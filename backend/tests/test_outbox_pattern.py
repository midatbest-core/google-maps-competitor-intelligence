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
from app.models.outbox import OutboxMessage
from app.services.scrape_service import ScrapeService
from app.services.outbox_service import OutboxDispatcher, create_outbox_message
from app.core.security import create_access_token
from app.workers.main import _execute_scrape_job
from app.scraper.schemas import ScrapeResult


PROD_ORIGIN = "https://google-maps-competitor-intelligence.onrender.com"


@pytest.fixture
def outbox_test_env(db):
    from app.api.dependencies import get_db, get_current_user, get_current_workspace
    app.dependency_overrides[get_db] = lambda: db

    user = User(id=str(uuid4()), email="test_outbox@example.com", hashed_password="pw")
    ws = Workspace(id=str(uuid4()), name="WS Outbox")
    db.add_all([user, ws])
    db.commit()

    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_current_workspace] = lambda: ws

    member = WorkspaceMember(workspace_id=ws.id, user_id=user.id, role="OWNER")
    db.add(member)

    own_biz = BusinessProfile(
        id=str(uuid4()),
        business_name="Main Brand Outbox Cafe",
        google_maps_url="https://maps.google.com/?cid=outbox_main"
    )
    db.add(own_biz)
    db.flush()

    project = Project(
        id=str(uuid4()),
        name="Project Outbox Testing",
        workspace_id=ws.id,
        own_business_id=own_biz.id
    )
    db.add(project)
    db.commit()

    for i in range(1, 4):
        b = BusinessProfile(
            id=str(uuid4()),
            business_name=f"Outbox Competitor {i}",
            google_maps_url=f"https://maps.google.com/?cid=outbox_comp_{i}"
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
# 1. API crash after database commit but before Redis enqueue
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_api_crash_after_db_commit_before_redis_enqueue(outbox_test_env, db):
    """
    Scenario: The API process crashes immediately after committing the ScrapeRun
    and OutboxMessage to PostgreSQL. Redis was never contacted by the API request.
    Verification:
    - ScrapeRun exists in DB with status QUEUED.
    - OutboxMessage exists in DB with status PENDING.
    - Subsequent dispatcher run discovers the pending message and dispatches to Redis.
    """
    project_id = outbox_test_env["project"].id
    service = ScrapeService(db, workspace=outbox_test_env["ws"])

    # Atomically create ScrapeRun and OutboxMessage
    run = service.create_scrape_run(project_id)
    run_id = run.id

    # Verify both exist in DB
    msg = db.query(OutboxMessage).filter(
        OutboxMessage.event_type == "SCRAPE_RUN_DISPATCH",
        OutboxMessage.status == "PENDING"
    ).first()
    assert msg is not None
    assert msg.payload.get("run_id") == run_id

    # Simulate API crash: process died before any Redis enqueue took place.
    # Later, background dispatcher wakes up:
    mock_pool = AsyncMock()
    mock_pool.enqueue_job = AsyncMock(return_value=MagicMock(job_id=f"scrape_{run_id}"))

    dispatcher = OutboxDispatcher(pool=mock_pool)
    dispatched_count = await dispatcher.dispatch_pending(db)

    assert dispatched_count == 1
    db.refresh(msg)
    assert msg.status == "DISPATCHED"
    assert msg.dispatched_at is not None
    mock_pool.enqueue_job.assert_awaited_once_with(
        "scrape_job", run_id, _job_id=f"scrape_{run_id}"
    )


# ---------------------------------------------------------------------------
# 2. Dispatcher restart with pending records
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_dispatcher_restart_with_pending_records(outbox_test_env, db):
    """
    Scenario: Multiple outbox records remain PENDING when the application restarts.
    Verification:
    - Application startup / dispatcher restart flushes all pending records.
    - Deterministic ARQ job IDs are assigned.
    - All messages marked DISPATCHED.
    """
    project_id = outbox_test_env["project"].id

    # Create 3 runs with outbox messages left in PENDING
    service = ScrapeService(db, workspace=outbox_test_env["ws"])
    run1 = service.create_scrape_run(project_id)
    # Mark run1 FAILED so we can create run2
    run1.status = "FAILED"
    db.commit()

    run2 = service.create_scrape_run(project_id)
    run2.status = "FAILED"
    db.commit()

    pending_before = db.query(OutboxMessage).filter(OutboxMessage.status == "PENDING").all()
    assert len(pending_before) >= 2

    mock_pool = AsyncMock()
    mock_pool.enqueue_job = AsyncMock(return_value=MagicMock(job_id="test_job"))

    dispatcher = OutboxDispatcher(pool=mock_pool)
    dispatched_count = await dispatcher.dispatch_pending(db)

    assert dispatched_count >= 2
    pending_after = db.query(OutboxMessage).filter(OutboxMessage.status == "PENDING").all()
    assert len(pending_after) == 0


# ---------------------------------------------------------------------------
# 3. Redis outage followed by recovery
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_redis_outage_followed_by_recovery(outbox_test_env, db):
    """
    Scenario:
    1. Outbox message created while Redis is completely unreachable.
    2. Initial dispatch attempt fails -> backoff scheduled, status remains PENDING.
    3. ScrapeRun remains safely QUEUED (not aborted).
    4. Redis recovers -> subsequent dispatch attempt succeeds -> status DISPATCHED.
    """
    project_id = outbox_test_env["project"].id
    service = ScrapeService(db, workspace=outbox_test_env["ws"])
    run = service.create_scrape_run(project_id)

    msg = db.query(OutboxMessage).filter(
        OutboxMessage.event_type == "SCRAPE_RUN_DISPATCH",
        OutboxMessage.status == "PENDING"
    ).first()
    assert msg.attempts == 0

    # 1. First attempt: Redis is DOWN
    failing_dispatcher = OutboxDispatcher()
    with patch.object(failing_dispatcher, "_get_pool", side_effect=Exception("Redis connection refused")):
        success = await failing_dispatcher.dispatch_message(db, msg)
        assert success is False

    db.refresh(msg)
    assert msg.status == "PENDING"
    assert msg.attempts == 1
    assert msg.next_attempt_at is not None
    assert "Redis connection refused" in msg.error_message

    # ScrapeRun is still QUEUED, not lost or prematurely killed
    db.refresh(run)
    assert run.status == "QUEUED"

    # 2. Redis RECOVERS
    # Advance time to satisfy backoff
    msg.next_attempt_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    db.commit()

    recovering_pool = AsyncMock()
    recovering_pool.enqueue_job = AsyncMock(return_value=MagicMock(job_id=f"scrape_{run.id}"))

    recovering_dispatcher = OutboxDispatcher(pool=recovering_pool)
    success = await recovering_dispatcher.dispatch_message(db, msg, pool=recovering_pool)
    assert success is True

    db.refresh(msg)
    assert msg.status == "DISPATCHED"
    assert msg.dispatched_at is not None
    assert msg.error_message is None


# ---------------------------------------------------------------------------
# 4. Duplicate outbox dispatch
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_duplicate_outbox_dispatch(outbox_test_env, db):
    """
    Scenario: An outbox record is dispatched twice concurrently or retried after
    already being queued.
    Verification:
    - Deterministic ARQ job ID (_job_id=f"scrape_{run_id}") deduplicates.
    - Redis returns None for the duplicate enqueue.
    - Both dispatches complete safely without double worker execution.
    """
    run_id = str(uuid4())
    msg = create_outbox_message(db, "SCRAPE_RUN_DISPATCH", {"run_id": run_id})
    db.commit()

    enqueued_jobs = {}
    async def mock_enqueue(func_name, *args, **kwargs):
        job_id = kwargs.get("_job_id")
        if job_id in enqueued_jobs:
            return None  # ARQ native behavior when job with _job_id already exists
        mock_job = MagicMock(job_id=job_id)
        enqueued_jobs[job_id] = mock_job
        return mock_job

    mock_pool = AsyncMock()
    mock_pool.enqueue_job = AsyncMock(side_effect=mock_enqueue)

    dispatcher = OutboxDispatcher(pool=mock_pool)

    # First dispatch
    success1 = await dispatcher.dispatch_message(db, msg, pool=mock_pool)
    assert success1 is True
    assert len(enqueued_jobs) == 1

    # Second (duplicate) dispatch of the same message or duplicate trigger
    msg.status = "PENDING"
    db.commit()
    success2 = await dispatcher.dispatch_message(db, msg, pool=mock_pool)
    assert success2 is True
    # Still exactly one active job in Redis
    assert len(enqueued_jobs) == 1


# ---------------------------------------------------------------------------
# 5. Worker crash and job retry
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_worker_crash_and_job_retry(outbox_test_env, db):
    """
    Scenario: Worker crashes while processing business 2 out of 3.
    Upon retry/restart:
    - Business 1 (SUCCESS) is preserved and not re-scraped.
    - Businesses 2 and 3 are processed to completion.
    - Run status successfully transitions to SUCCESS.
    """
    project_id = outbox_test_env["project"].id
    service = ScrapeService(db, workspace=outbox_test_env["ws"])
    run = service.create_scrape_run(project_id)
    run_id = run.id

    comps = db.query(ScrapeRunCompetitor).filter(ScrapeRunCompetitor.scrape_run_id == run_id).all()
    assert len(comps) == 3

    # Business 1 succeeded before crash
    comps[0].status = "SUCCESS"
    comps[0].posts_discovered = 2
    # Business 2 failed during crash
    comps[1].status = "FAILED"
    comps[1].error_message = "Process killed by OOM"
    # Business 3 remained PENDING
    comps[2].status = "PENDING"
    db.commit()

    scraped_urls = []
    class CrashRecoveryAdapter:
        async def scrape(self, target_url: str):
            scraped_urls.append(target_url)
            return ScrapeResult(status="SUCCESS", posts=[])
        async def close(self): pass

    ctx = {"scraper_adapter": CrashRecoveryAdapter()}
    worker_db = MagicMock(wraps=db)
    worker_db.close = MagicMock()

    with patch("app.workers.main.SessionLocal", return_value=worker_db):
        await _execute_scrape_job(ctx, run_id)

    db.refresh(run)
    assert run.status == "SUCCESS"
    # Business 1 was already SUCCESS, so only Businesses 2 and 3 were scraped
    assert len(scraped_urls) == 2
    assert comps[0].business.google_maps_url not in scraped_urls


# ---------------------------------------------------------------------------
# 6. Concurrent dispatcher execution (skip_locked)
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_concurrent_dispatcher_execution_skip_locked(outbox_test_env, db):
    """
    Scenario: Multiple instances of OutboxDispatcher run dispatch_pending concurrently.
    Verification:
    - Each pending record is dispatched without race conditions or duplicate execution.
    - Lock handling prevents conflicting state transitions.
    """
    # Create 5 outbox messages
    for i in range(5):
        create_outbox_message(db, "SCRAPE_RUN_DISPATCH", {"run_id": f"run_{i}"})
    db.commit()

    dispatched_run_ids = []
    async def mock_enqueue(func_name, *args, **kwargs):
        run_id = args[0]
        dispatched_run_ids.append(run_id)
        return MagicMock(job_id=kwargs.get("_job_id"))

    mock_pool = AsyncMock()
    mock_pool.enqueue_job = AsyncMock(side_effect=mock_enqueue)

    dispatcher1 = OutboxDispatcher(pool=mock_pool)
    dispatcher2 = OutboxDispatcher(pool=mock_pool)

    # Run dispatchers concurrently
    results = await asyncio.gather(
        dispatcher1.dispatch_pending(db, limit=3),
        dispatcher2.dispatch_pending(db, limit=3)
    )

    total_dispatched = sum(results)
    assert total_dispatched == 5
    assert len(dispatched_run_ids) == 5
    # All 5 unique runs dispatched
    assert len(set(dispatched_run_ids)) == 5

    pending_remaining = db.query(OutboxMessage).filter(OutboxMessage.status == "PENDING").count()
    assert pending_remaining == 0


# ---------------------------------------------------------------------------
# 7. No duplicate competitor processing on resume
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_no_duplicate_competitor_processing_on_resume(outbox_test_env, db):
    """
    Scenario: A scrape run has completed some competitors (SUCCESS and NO_DATA)
    and failed on another.
    Verification:
    - Resuming the run does NOT re-scrape competitors with SUCCESS or NO_DATA.
    - Only PENDING or FAILED competitors are executed.
    """
    project_id = outbox_test_env["project"].id
    service = ScrapeService(db, workspace=outbox_test_env["ws"])
    run = service.create_scrape_run(project_id)
    run_id = run.id

    comps = db.query(ScrapeRunCompetitor).filter(ScrapeRunCompetitor.scrape_run_id == run_id).all()
    comps[0].status = "SUCCESS"
    comps[1].status = "NO_DATA"
    comps[2].status = "FAILED"
    comps[2].error_message = "HTTP 429 Too Many Requests"
    run.status = "FAILED"
    db.commit()

    # Resume the run
    resumed_run = service.resume_run(run_id)
    assert resumed_run.status == "QUEUED"

    # Outbox message was generated for the resume
    resume_msg = db.query(OutboxMessage).filter(
        OutboxMessage.event_type == "SCRAPE_RUN_DISPATCH",
        OutboxMessage.status == "PENDING"
    ).order_by(OutboxMessage.created_at.desc()).first()
    assert resume_msg is not None
    assert resume_msg.payload.get("run_id") == run_id

    # Execute worker on resumed run
    scraped_urls = []
    class ResumeTrackingAdapter:
        async def scrape(self, target_url: str):
            scraped_urls.append(target_url)
            return ScrapeResult(status="SUCCESS", posts=[])
        async def close(self): pass

    ctx = {"scraper_adapter": ResumeTrackingAdapter()}
    worker_db = MagicMock(wraps=db)
    worker_db.close = MagicMock()

    with patch("app.workers.main.SessionLocal", return_value=worker_db):
        await _execute_scrape_job(ctx, run_id)

    db.refresh(resumed_run)
    assert resumed_run.status == "SUCCESS"

    # Verify only the previously FAILED competitor was re-scraped
    assert len(scraped_urls) == 1
    assert scraped_urls[0] == comps[2].business.google_maps_url


# ---------------------------------------------------------------------------
# 8. Terminal failure marks ScrapeRun as FAILED
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_terminal_failure_marks_run_failed(outbox_test_env, db):
    """
    Scenario: Redis remains down and outbox attempts exceed max_attempts.
    Verification:
    - OutboxMessage status transitions to FAILED.
    - ScrapeRun status transitions to FAILED.
    - ScrapeRun error_logs records the terminal failure reason.
    - No runs remain indefinitely in QUEUED.
    """
    project_id = outbox_test_env["project"].id
    service = ScrapeService(db, workspace=outbox_test_env["ws"])
    run = service.create_scrape_run(project_id)

    msg = db.query(OutboxMessage).filter(
        OutboxMessage.event_type == "SCRAPE_RUN_DISPATCH",
        OutboxMessage.status == "PENDING"
    ).first()

    # Set attempts to max_attempts - 1 so the next attempt is the final one
    msg.attempts = msg.max_attempts - 1
    db.commit()

    dispatcher = OutboxDispatcher()
    with patch.object(dispatcher, "_get_pool", side_effect=Exception("Terminal redis crash")):
        success = await dispatcher.dispatch_message(db, msg)
        assert success is False

    db.refresh(msg)
    assert msg.status == "FAILED"
    assert msg.attempts == msg.max_attempts

    db.refresh(run)
    assert run.status == "FAILED"
    assert "terminal failure" in run.error_logs[0].lower()
