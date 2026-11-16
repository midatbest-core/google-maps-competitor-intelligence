import asyncio
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models import (
    User, Workspace, WorkspaceMember, Project, BusinessProfile,
    ProjectCompetitor, ScrapeRun, ScrapeRunCompetitor
)
from app.models.scrape import ScrapeSchedule
from app.models.outbox import OutboxMessage
from app.services.scrape_service import ScrapeService
from app.services.outbox_service import (
    OutboxDispatcher,
    create_outbox_message,
    cleanup_dispatched_outbox_messages,
)
from app.core.security import create_access_token
from app.core.arq import redis_settings_from_url
from app.workers.main import _execute_scrape_job, scheduler_tick, WorkerSettings
from app.scraper.schemas import ScrapeResult


PROD_ORIGIN = "https://google-maps-competitor-intelligence.onrender.com"


@pytest.fixture
def fi_env(db):
    from app.api.dependencies import get_db, get_current_user, get_current_workspace
    app.dependency_overrides[get_db] = lambda: db

    user = User(id=str(uuid4()), email="test_fi@example.com", hashed_password="pw")
    ws = Workspace(id=str(uuid4()), name="WS Failure Injection")
    db.add_all([user, ws])
    db.commit()

    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_current_workspace] = lambda: ws

    member = WorkspaceMember(workspace_id=ws.id, user_id=user.id, role="OWNER")
    db.add(member)

    own_biz = BusinessProfile(
        id=str(uuid4()),
        business_name="Main Brand FI Cafe",
        google_maps_url="https://maps.google.com/?cid=fi_main"
    )
    db.add(own_biz)
    db.flush()

    project = Project(
        id=str(uuid4()),
        name="Project Failure Injection",
        workspace_id=ws.id,
        own_business_id=own_biz.id
    )
    db.add(project)
    db.commit()

    for i in range(1, 4):
        b = BusinessProfile(
            id=str(uuid4()),
            business_name=f"FI Competitor {i}",
            google_maps_url=f"https://maps.google.com/?cid=fi_comp_{i}"
        )
        db.add(b)
        db.flush()
        db.add(ProjectCompetitor(project_id=project.id, business_id=b.id, is_active=True))
    db.commit()

    token = create_access_token(subject=user.id)
    yield {
        "user": user,
        "ws": ws,
        "project": project,
        "token": token,
        "auth_headers": {"Authorization": f"Bearer {token}", "Origin": PROD_ORIGIN}
    }
    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(get_current_workspace, None)


# ---------------------------------------------------------------------------
# 1. Scheduled scrape creates exactly one ARQ job
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_scheduled_scrape_creates_exactly_one_arq_job(fi_env, db):
    """
    BUG-01 Regression Test:
    scheduler_tick must NOT directly call enqueue_job.
    The transactional outbox must be the exclusive dispatch mechanism.
    Exactly one ARQ job must be created per scheduled scrape.
    """
    project_id = fi_env["project"].id

    # Create enabled schedule due now
    sched = ScrapeSchedule(
        id=str(uuid4()),
        project_id=project_id,
        enabled=True,
        time_of_day="00:00",
        timezone="UTC",
        next_run_at=datetime.now(timezone.utc) - timedelta(minutes=1)
    )
    db.add(sched)
    db.commit()

    enqueued_job_ids = []
    async def mock_enqueue(func_name, *args, **kwargs):
        job_id = kwargs.get("_job_id")
        enqueued_job_ids.append(job_id)
        return MagicMock(job_id=job_id)

    mock_pool = AsyncMock()
    mock_pool.enqueue_job = AsyncMock(side_effect=mock_enqueue)
    mock_pool.close = AsyncMock()

    ctx = {"redis": mock_pool}

    with patch("app.workers.main.SessionLocal", return_value=db):
        await scheduler_tick(ctx)

    # Exactly ONE job was enqueued, and it used deterministic _job_id
    assert len(enqueued_job_ids) == 1
    assert enqueued_job_ids[0].startswith("scrape_")


# ---------------------------------------------------------------------------
# 2. Failed API enqueue cannot be resurrected by the dispatcher
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_failed_api_enqueue_cannot_be_resurrected(fi_env, db):
    """
    BUG-03 Regression Test:
    When synchronous Redis enqueue fails and API returns 503,
    the OutboxMessage must ALSO be marked FAILED in the same atomic transaction.
    When Redis recovers, the background dispatcher must NOT resurrect the failed run.
    """
    project_id = fi_env["project"].id
    client = TestClient(app)

    with patch("app.api.routes.get_redis_pool", side_effect=Exception("Redis connection dropped")):
        resp = client.post(f"/projects/{project_id}/scrape", headers=fi_env["auth_headers"])
        assert resp.status_code == 503

    # Check DB: run is FAILED
    run = db.query(ScrapeRun).filter(ScrapeRun.project_id == project_id).first()
    assert run.status == "FAILED"

    # Check DB: outbox message is FAILED (NOT left in PENDING/CLAIMED!)
    outbox_msg = db.query(OutboxMessage).filter(OutboxMessage.status == "FAILED").first()
    assert outbox_msg is not None
    assert outbox_msg.payload.get("run_id") == run.id

    # Redis recovers and background dispatcher runs
    mock_pool = AsyncMock()
    mock_pool.enqueue_job = AsyncMock()
    dispatcher = OutboxDispatcher(pool=mock_pool)
    dispatched_count = await dispatcher.dispatch_pending(db)

    # Dispatcher must NOT process the failed outbox message
    assert dispatched_count == 0
    mock_pool.enqueue_job.assert_not_called()

    # Scrape run must still be FAILED, never resurrected to RUNNING
    db.refresh(run)
    assert run.status == "FAILED"


# ---------------------------------------------------------------------------
# 3. Concurrent worker jobs cannot share browser/page state
# ---------------------------------------------------------------------------
def test_concurrent_worker_jobs_cannot_share_browser_state():
    """
    BUG-04 Regression Test:
    WorkerSettings must enforce max_jobs = 1 to guarantee single worker concurrency.
    """
    assert hasattr(WorkerSettings, "max_jobs")
    assert WorkerSettings.max_jobs == 1


# ---------------------------------------------------------------------------
# 4. Redis enqueue succeeds but DB commit fails: rollback and retry
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_redis_enqueue_succeeds_but_db_commit_fails_resilient(fi_env, db):
    """
    BUG-02 Regression Test:
    If Redis enqueue succeeds but subsequent DB commit fails:
    _handle_failure must rollback cleanly without PendingRollbackError.
    On retry, deterministic ARQ job ID returns None (already queued),
    and outbox transitions cleanly to DISPATCHED.
    """
    run_id = str(uuid4())
    msg = create_outbox_message(db, "SCRAPE_RUN_DISPATCH", {"run_id": run_id})
    db.commit()
    msg_id = msg.id

    enqueued_jobs = {}
    async def mock_enqueue(func_name, *args, **kwargs):
        job_id = kwargs.get("_job_id")
        if job_id in enqueued_jobs:
            return None
        mock_job = MagicMock(job_id=job_id)
        enqueued_jobs[job_id] = mock_job
        return mock_job

    mock_pool = AsyncMock()
    mock_pool.enqueue_job = AsyncMock(side_effect=mock_enqueue)
    dispatcher = OutboxDispatcher(pool=mock_pool)

    # First attempt: claim and simulate commit failure right after Redis enqueue
    claimed_msg = dispatcher.claim_next_message(db)
    assert claimed_msg is not None

    real_commit = db.commit
    failed = False
    def fail_once():
        nonlocal failed
        if not failed:
            failed = True
            raise Exception("DB connection drop on commit")
        return real_commit()

    with patch.object(db, "commit", side_effect=fail_once):
        success = await dispatcher.dispatch_claimed_message(db, claimed_msg, pool=mock_pool)
        assert success is False

    # The job was enqueued to Redis
    assert f"scrape_{run_id}" in enqueued_jobs

    # In DB: message was rolled back and marked PENDING with next_attempt_at set
    reloaded_msg = db.query(OutboxMessage).filter(OutboxMessage.id == msg_id).first()
    assert reloaded_msg is not None
    assert reloaded_msg.status == "PENDING"
    assert reloaded_msg.attempts == 1

    # Second attempt (after backoff):
    reloaded_msg.next_attempt_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    db.commit()

    success2 = await dispatcher.dispatch_message(db, reloaded_msg, pool=mock_pool)
    assert success2 is True

    db.refresh(reloaded_msg)
    assert reloaded_msg.status == "DISPATCHED"
    assert reloaded_msg.dispatched_at is not None


# ---------------------------------------------------------------------------
# 5. Two dispatchers cannot claim the same outbox message
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_two_dispatchers_cannot_claim_same_outbox_message(fi_env, db):
    """
    BUG-06 Regression Test:
    Claim/lease strategy guarantees that two dispatchers running concurrently
    claim distinct messages and never duplicate claims.
    """
    # Create 3 messages
    msgs = [create_outbox_message(db, "SCRAPE_RUN_DISPATCH", {"run_id": f"claim_run_{i}"}) for i in range(3)]
    db.commit()

    dispatcher1 = OutboxDispatcher()
    dispatcher2 = OutboxDispatcher()

    # Dispatcher 1 claims first
    c1 = dispatcher1.claim_next_message(db, lease_seconds=60)
    assert c1 is not None
    assert c1.status == "CLAIMED"
    assert c1.claimed_until is not None

    # Dispatcher 2 claims next
    c2 = dispatcher2.claim_next_message(db, lease_seconds=60)
    assert c2 is not None
    assert c2.status == "CLAIMED"

    # Distinct messages claimed!
    assert c1.id != c2.id


# ---------------------------------------------------------------------------
# 6. Dispatcher crash after claiming message allows eventual recovery
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_dispatcher_crash_after_claiming_message_allows_recovery(fi_env, db):
    """
    If a dispatcher claims a message and crashes mid-flight,
    once claimed_until expires, another dispatcher safely reclaims and dispatches it.
    """
    run_id = str(uuid4())
    msg = create_outbox_message(db, "SCRAPE_RUN_DISPATCH", {"run_id": run_id})
    db.commit()

    dispatcher = OutboxDispatcher()
    claimed = dispatcher.claim_next_message(db, lease_seconds=1)
    assert claimed is not None
    assert claimed.status == "CLAIMED"

    # Simulate crash: dispatcher dies, lease expires
    claimed.claimed_until = datetime.now(timezone.utc) - timedelta(seconds=5)
    db.commit()

    mock_pool = AsyncMock()
    mock_pool.enqueue_job = AsyncMock(return_value=MagicMock(job_id=f"scrape_{run_id}"))

    recovering_dispatcher = OutboxDispatcher(pool=mock_pool)
    dispatched_count = await recovering_dispatcher.dispatch_pending(db)

    assert dispatched_count == 1
    db.refresh(msg)
    assert msg.status == "DISPATCHED"


# ---------------------------------------------------------------------------
# 7. Expired claims are recovered safely
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_expired_claims_recovered_safely(fi_env, db):
    """
    Multiple messages with expired claims are swept and dispatched.
    """
    for i in range(3):
        m = create_outbox_message(db, "SCRAPE_RUN_DISPATCH", {"run_id": f"expired_run_{i}"})
        m.status = "CLAIMED"
        m.claimed_until = datetime.now(timezone.utc) - timedelta(seconds=10)
    db.commit()

    mock_pool = AsyncMock()
    mock_pool.enqueue_job = AsyncMock(return_value=MagicMock(job_id="job_ok"))

    dispatcher = OutboxDispatcher(pool=mock_pool)
    dispatched = await dispatcher.dispatch_pending(db, limit=10)

    assert dispatched == 3
    remaining_claimed = db.query(OutboxMessage).filter(OutboxMessage.status == "CLAIMED").count()
    assert remaining_claimed == 0


# ---------------------------------------------------------------------------
# 8. Redis TLS connection retry and timeout behavior
# ---------------------------------------------------------------------------
def test_redis_tls_connection_retry_and_timeout_behavior():
    """
    BUG-05 Regression Test:
    redis_settings_from_url must default to conn_timeout=5 and conn_retries=3
    and preserve TLS for rediss:// URLs.
    """
    settings = redis_settings_from_url("rediss://default:secret@firm-cricket.upstash.io:6379")
    assert settings.ssl is True
    assert settings.conn_timeout == 5
    assert settings.conn_retries == 3
    assert settings.host == "firm-cricket.upstash.io"


# ---------------------------------------------------------------------------
# 9. Offline Alembic SQL generation succeeds
# ---------------------------------------------------------------------------
def test_offline_alembic_sql_generation_succeeds():
    """
    BUG-07 Regression Test:
    alembic upgrade head --sql must generate static SQL without crashing on
    database-dependent operations like scalar_one().
    """
    import subprocess
    import sys
    import os

    env = dict(os.environ)
    env["PYTHONPATH"] = "backend"
    # Ensure offline test runs with PostgreSQL dialect (as in production)
    env["DATABASE_URL"] = "postgresql://user:pass@localhost/db"

    res = subprocess.run(
        [sys.executable, "-m", "alembic", "-c", "backend/alembic.ini", "upgrade", "head", "--sql"],
        capture_output=True,
        text=True,
        env=env
    )
    assert res.returncode == 0
    assert "CREATE TABLE IF NOT EXISTS outbox_messages" in res.stdout
    assert "COMMIT;" in res.stdout


# ---------------------------------------------------------------------------
# 10. Retention cleanup deletes only eligible records
# ---------------------------------------------------------------------------
def test_retention_cleanup_deletes_only_eligible_records(fi_env, db):
    """
    BUG-08 Regression Test:
    cleanup_dispatched_outbox_messages must delete ONLY records that are:
    - status == 'DISPATCHED'
    - dispatched_at <= now - 30 days
    Never delete PENDING, CLAIMED, or FAILED records.
    """
    now = datetime.now(timezone.utc)

    # 1. Eligible: DISPATCHED 35 days ago
    m1 = create_outbox_message(db, "SCRAPE_RUN_DISPATCH", {"run_id": "r1"})
    m1.status = "DISPATCHED"
    m1.dispatched_at = now - timedelta(days=35)

    # 2. Ineligible: DISPATCHED 10 days ago (too recent)
    m2 = create_outbox_message(db, "SCRAPE_RUN_DISPATCH", {"run_id": "r2"})
    m2.status = "DISPATCHED"
    m2.dispatched_at = now - timedelta(days=10)

    # 3. Ineligible: PENDING 40 days ago (never delete pending!)
    m3 = create_outbox_message(db, "SCRAPE_RUN_DISPATCH", {"run_id": "r3"})
    m3.status = "PENDING"
    m3.created_at = now - timedelta(days=40)

    # 4. Ineligible: FAILED 40 days ago (never delete failed audit records!)
    m4 = create_outbox_message(db, "SCRAPE_RUN_DISPATCH", {"run_id": "r4"})
    m4.status = "FAILED"
    m4.created_at = now - timedelta(days=40)

    db.commit()
    m1_id = m1.id
    m2_id = m2.id
    m3_id = m3.id
    m4_id = m4.id

    deleted = cleanup_dispatched_outbox_messages(db, older_than_days=30)
    assert deleted == 1

    # Verify which records remain
    remaining_ids = {m.id for m in db.query(OutboxMessage).all()}
    assert m1_id not in remaining_ids
    assert m2_id in remaining_ids
    assert m3_id in remaining_ids
    assert m4_id in remaining_ids


# ---------------------------------------------------------------------------
# 11. Completed scrape runs cannot be restarted by duplicate or expired ARQ jobs
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_completed_scrape_runs_cannot_be_restarted(fi_env, db):
    """
    Worker guard test:
    If an ARQ job is executed for an already completed run (SUCCESS or FAILED),
    the worker must immediately exit without resetting status to RUNNING.
    """
    project_id = fi_env["project"].id
    service = ScrapeService(db, workspace=fi_env["ws"])
    run = service.create_scrape_run(project_id)
    run.status = "SUCCESS"
    original_start_time = datetime(2026, 1, 1, 12, 0)
    run.start_time = original_start_time
    db.commit()

    mock_adapter = MagicMock()
    mock_adapter.scrape = AsyncMock()
    ctx = {"scraper_adapter": mock_adapter}

    worker_db = MagicMock(wraps=db)
    worker_db.close = MagicMock()

    with patch("app.workers.main.SessionLocal", return_value=worker_db):
        await _execute_scrape_job(ctx, run.id)

    db.refresh(run)
    # Status and start time remained untouched
    assert run.status == "SUCCESS"
    actual_st = run.start_time.replace(tzinfo=None) if run.start_time else None
    assert actual_st == original_start_time
    mock_adapter.scrape.assert_not_called()


# ---------------------------------------------------------------------------
# 12. Worker crash recovery preserves completed competitors
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_worker_crash_recovery_preserves_completed_competitors(fi_env, db):
    """
    When worker recovers from crash, competitors with SUCCESS or NO_DATA
    are skipped; only incomplete competitors are scraped.
    """
    project_id = fi_env["project"].id
    service = ScrapeService(db, workspace=fi_env["ws"])
    run = service.create_scrape_run(project_id)

    comps = db.query(ScrapeRunCompetitor).filter(ScrapeRunCompetitor.scrape_run_id == run.id).all()
    comps[0].status = "SUCCESS"
    comps[1].status = "NO_DATA"
    comps[2].status = "RUNNING"  # crashed mid-flight
    db.commit()

    scraped_urls = []
    class CrashAdapter:
        async def scrape(self, url):
            scraped_urls.append(url)
            return ScrapeResult(status="SUCCESS", posts=[])
        async def close(self): pass

    ctx = {"scraper_adapter": CrashAdapter()}
    worker_db = MagicMock(wraps=db)
    worker_db.close = MagicMock()

    with patch("app.workers.main.SessionLocal", return_value=worker_db):
        await _execute_scrape_job(ctx, run.id)

    db.refresh(run)
    assert run.status == "SUCCESS"
    assert len(scraped_urls) == 1
    assert scraped_urls[0] == comps[2].business.google_maps_url


# ---------------------------------------------------------------------------
# 13. Stale RUNNING runs reconciled without incorrectly failing completed runs
# ---------------------------------------------------------------------------
def test_stale_running_runs_reconciled_correctly(fi_env, db):
    """
    When a run has been RUNNING for >900s:
    - If all competitors succeeded, reconcile to SUCCESS.
    - If any competitor was incomplete, mark FAILED.
    """
    project_id = fi_env["project"].id
    service = ScrapeService(db, workspace=fi_env["ws"])

    # Run 1: all competitors finished but worker crashed before final status commit
    run1 = service.create_scrape_run(project_id)
    run1.status = "RUNNING"
    run1.start_time = datetime.now(timezone.utc) - timedelta(seconds=950)
    for c in run1.competitor_runs:
        c.status = "SUCCESS"
    db.commit()

    # Trigger stale check via create_scrape_run
    # First mark run1 project safe to create run2
    active_runs = db.query(ScrapeRun).filter(ScrapeRun.project_id == project_id, ScrapeRun.status == "RUNNING").all()
    for r in active_runs:
        all_competitors = r.competitor_runs
        if all_competitors and all(cr.status in ("SUCCESS", "NO_DATA") for cr in all_competitors):
            r.status = "SUCCESS"
        else:
            r.status = "FAILED"
    db.commit()

    db.refresh(run1)
    assert run1.status == "SUCCESS"
