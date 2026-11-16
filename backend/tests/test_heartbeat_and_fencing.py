import asyncio
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4
import pytest

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
)
from app.workers.main import _execute_scrape_job, scheduler_tick
from app.scraper.schemas import ScrapeResult
from tests.conftest import TestingSessionLocal


@pytest.fixture
def hf_env(db):
    user = User(id=str(uuid4()), email="test_hf@example.com", hashed_password="pw")
    ws = Workspace(id=str(uuid4()), name="WS Heartbeat Fencing")
    db.add_all([user, ws])
    db.commit()

    member = WorkspaceMember(workspace_id=ws.id, user_id=user.id, role="OWNER")
    db.add(member)

    own_biz = BusinessProfile(
        id=str(uuid4()),
        business_name="Heartbeat Main Cafe",
        google_maps_url="https://maps.google.com/?cid=hf_main"
    )
    db.add(own_biz)
    db.flush()

    project = Project(
        id=str(uuid4()),
        name="Project Heartbeat Fencing",
        workspace_id=ws.id,
        own_business_id=own_biz.id
    )
    db.add(project)
    db.commit()

    for i in range(1, 4):
        b = BusinessProfile(
            id=str(uuid4()),
            business_name=f"HF Competitor {i}",
            google_maps_url=f"https://maps.google.com/?cid=hf_comp_{i}"
        )
        db.add(b)
        db.flush()
        db.add(ProjectCompetitor(project_id=project.id, business_id=b.id, is_active=True))
    db.commit()

    return {
        "user": user,
        "ws": ws,
        "project": project,
    }


# ===========================================================================
# HEARTBEAT & STALE RUN RECONCILIATION TESTS
# ===========================================================================

@pytest.mark.asyncio
async def test_healthy_scrape_running_longer_than_15_minutes_not_terminated(hf_env, db):
    """
    BUG-01: A healthy scrape run started 25 minutes ago (>900s) whose heartbeat
    was refreshed 30 seconds ago (<300s) must NOT be terminated by scheduler_tick.
    """
    project_id = hf_env["project"].id
    service = ScrapeService(db, workspace=hf_env["ws"])
    run = service.create_scrape_run(project_id)

    now = datetime.now(timezone.utc)
    # Run started 25 minutes ago (1500 seconds ago)
    run.status = "RUNNING"
    run.start_time = now - timedelta(minutes=25)
    # Healthy heartbeat refreshed 20 seconds ago
    run.heartbeat_at = now - timedelta(seconds=20)
    db.commit()

    # Create due schedule
    sched = ScrapeSchedule(
        id=str(uuid4()),
        project_id=project_id,
        enabled=True,
        time_of_day="00:00",
        timezone="UTC",
        next_run_at=now - timedelta(minutes=1)
    )
    db.add(sched)
    db.commit()

    mock_pool = AsyncMock()
    mock_pool.enqueue_job = AsyncMock()
    ctx = {"redis": mock_pool}

    worker_db = MagicMock(wraps=db)
    worker_db.close = MagicMock()

    with patch("app.workers.main.SessionLocal", return_value=worker_db):
        await scheduler_tick(ctx)

    db.expire_all()
    run = db.query(ScrapeRun).filter(ScrapeRun.id == run.id).first()
    # Run MUST remain RUNNING; scheduler must NOT mark it FAILED!
    assert run.status == "RUNNING"
    assert run.end_time is None

    # Scheduler must NOT create a second duplicate scrape run
    total_runs = db.query(ScrapeRun).filter(ScrapeRun.project_id == project_id).count()
    assert total_runs == 1


@pytest.mark.asyncio
async def test_heartbeat_refreshes_during_processing(hf_env, db):
    """
    BUG-01: Worker must update heartbeat_at when starting execution
    and refresh it during competitor processing.
    """
    project_id = hf_env["project"].id
    service = ScrapeService(db, workspace=hf_env["ws"])
    run = service.create_scrape_run(project_id)

    initial_time = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
    run.heartbeat_at = initial_time
    db.commit()

    class MockAdapter:
        async def scrape(self, target_url: str):
            await asyncio.sleep(0.01)
            return ScrapeResult(status="SUCCESS", posts=[])
        async def close(self): pass

    ctx = {"scraper_adapter": MockAdapter()}
    worker_db = MagicMock(wraps=db)
    worker_db.close = MagicMock()

    with patch("app.workers.main.SessionLocal", return_value=worker_db):
        await _execute_scrape_job(ctx, run.id)

    db.expire_all()
    run = db.query(ScrapeRun).filter(ScrapeRun.id == run.id).first()
    assert run.status == "SUCCESS"
    assert run.heartbeat_at is not None
    # Heartbeat was updated past the initial placeholder time
    actual_hb = run.heartbeat_at.replace(tzinfo=timezone.utc) if run.heartbeat_at.tzinfo is None else run.heartbeat_at
    assert actual_hb > initial_time


def test_genuinely_expired_heartbeat_is_recovered(hf_env, db):
    """
    BUG-01: When worker crashes and heartbeat is dead for >300s (5 minutes),
    create_scrape_run safely reconciles the dead run.
    """
    project_id = hf_env["project"].id
    service = ScrapeService(db, workspace=hf_env["ws"])
    run = service.create_scrape_run(project_id)

    now = datetime.now(timezone.utc)
    run.status = "RUNNING"
    run.start_time = now - timedelta(minutes=10)
    # Heartbeat dead for 8 minutes (>300s)
    run.heartbeat_at = now - timedelta(minutes=8)

    comps = run.competitor_runs
    comps[0].status = "SUCCESS"
    comps[1].status = "RUNNING"
    comps[2].status = "PENDING"
    db.commit()

    # create_scrape_run detects expired heartbeat and reconciles
    new_run = service.create_scrape_run(project_id)

    db.refresh(run)
    # Because competitor 1 succeeded, run reconciled to PARTIAL_SUCCESS (or FAILED)
    assert run.status in ("PARTIAL_SUCCESS", "FAILED")
    assert run.end_time is not None
    # Abandoned RUNNING competitor was marked FAILED
    db.refresh(comps[1])
    assert comps[1].status == "FAILED"
    assert "interrupted" in comps[1].error_message.lower()

    # New run created cleanly
    assert new_run.id != run.id
    assert new_run.status == "QUEUED"


def test_dead_worker_run_with_all_competitors_completed_reconciles_to_success(hf_env, db):
    """
    BUG-01: If all competitors finished with SUCCESS/NO_DATA but worker crashed
    before writing run.status = 'SUCCESS', stale reconciliation marks it SUCCESS.
    """
    project_id = hf_env["project"].id
    service = ScrapeService(db, workspace=hf_env["ws"])
    run = service.create_scrape_run(project_id)

    now = datetime.now(timezone.utc)
    run.status = "RUNNING"
    run.start_time = now - timedelta(minutes=10)
    run.heartbeat_at = now - timedelta(minutes=6) # dead > 300s

    for c in run.competitor_runs:
        c.status = "SUCCESS"
    db.commit()

    new_run = service.create_scrape_run(project_id)
    db.refresh(run)
    assert run.status == "SUCCESS"
    assert run.end_time is not None
    assert new_run.status == "QUEUED"


def test_stale_scheduler_cannot_terminate_worker_with_valid_heartbeat(hf_env, db):
    """
    BUG-01: An active scrape with a valid heartbeat (updated 10s ago)
    cannot be terminated by create_scrape_run; raises ValueError (409 Conflict).
    """
    project_id = hf_env["project"].id
    service = ScrapeService(db, workspace=hf_env["ws"])
    run = service.create_scrape_run(project_id)

    now = datetime.now(timezone.utc)
    run.status = "RUNNING"
    run.start_time = now - timedelta(minutes=20) # Total run time 20 mins!
    run.heartbeat_at = now - timedelta(seconds=10) # Heartbeat active!
    db.commit()

    with pytest.raises(ValueError, match="already has an active run"):
        service.create_scrape_run(project_id)

    db.expire_all()
    run = db.query(ScrapeRun).filter(ScrapeRun.id == run.id).first()
    assert run.status == "RUNNING"


# ===========================================================================
# OUTBOX FENCING & CLAIM TOKEN TESTS
# ===========================================================================

@pytest.mark.asyncio
async def test_dispatcher_a_lease_expires_and_dispatcher_b_dispatches_cleanly(hf_env, db):
    """
    BUG-02: Dispatcher A claims a message. Lease expires.
    Dispatcher B reclaims it with a new claim_token and dispatches it.
    """
    run_id = str(uuid4())
    msg = create_outbox_message(db, "SCRAPE_RUN_DISPATCH", {"run_id": run_id})
    db.commit()

    dispatcher_a = OutboxDispatcher()
    dispatcher_b = OutboxDispatcher()

    # Dispatcher A claims with 1-second lease
    claimed_a = dispatcher_a.claim_next_message(db, lease_seconds=1)
    assert claimed_a is not None
    assert claimed_a.status == "CLAIMED"
    token_a = claimed_a.claim_token
    assert token_a is not None

    # Simulate lease expiration for Dispatcher A
    claimed_a.claimed_until = datetime.now(timezone.utc) - timedelta(seconds=5)
    db.commit()

    # Dispatcher B reclaims
    claimed_b = dispatcher_b.claim_next_message(db, lease_seconds=60)
    assert claimed_b is not None
    assert claimed_b.id == claimed_a.id
    token_b = claimed_b.claim_token
    assert token_b is not None
    assert token_a != token_b # Unique claim token issued!

    # Dispatcher B dispatches successfully
    mock_pool = AsyncMock()
    mock_pool.enqueue_job = AsyncMock(return_value=MagicMock(job_id=f"scrape_{run_id}"))

    success_b = await dispatcher_b.dispatch_claimed_message(db, claimed_b, pool=mock_pool)
    assert success_b is True

    db.refresh(msg)
    assert msg.status == "DISPATCHED"
    assert msg.dispatched_at is not None
    assert msg.claim_token is None


@pytest.mark.asyncio
async def test_stale_dispatcher_a_failure_update_is_rejected_after_b_dispatches(hf_env, db):
    """
    BUG-02: Dispatcher A's lease expired, Dispatcher B dispatched the message.
    Dispatcher A wakes up, encounters an error, and calls _handle_failure.
    Dispatcher A's stale update MUST be rejected.
    Message MUST remain DISPATCHED and NEVER regress to PENDING or FAILED.
    """
    run_id = str(uuid4())
    msg = create_outbox_message(db, "SCRAPE_RUN_DISPATCH", {"run_id": run_id})
    db.commit()

    dispatcher_a = OutboxDispatcher()
    dispatcher_b = OutboxDispatcher()

    # 1. Dispatcher A claims
    claimed_a = dispatcher_a.claim_next_message(db, lease_seconds=1)
    token_a = claimed_a.claim_token

    # 2. Lease expires
    claimed_a.claimed_until = datetime.now(timezone.utc) - timedelta(seconds=5)
    db.commit()

    # 3. Dispatcher B reclaims and dispatches
    claimed_b = dispatcher_b.claim_next_message(db, lease_seconds=60)
    mock_pool_b = AsyncMock()
    mock_pool_b.enqueue_job = AsyncMock(return_value=MagicMock(job_id=f"scrape_{run_id}"))
    await dispatcher_b.dispatch_claimed_message(db, claimed_b, pool=mock_pool_b)

    db.refresh(msg)
    assert msg.status == "DISPATCHED"

    # 4. Stale Dispatcher A wakes up and reports failure with its stale token_a
    mock_exc = Exception("Redis connection timeout in stale worker A")
    now = datetime.now(timezone.utc)
    res = dispatcher_a._handle_failure(db, claimed_a, mock_exc, now, claim_token=token_a)
    assert res is False

    # 5. VERIFY: Message status was NOT corrupted! Still DISPATCHED!
    db.refresh(msg)
    assert msg.status == "DISPATCHED"
    assert msg.dispatched_at is not None
    assert msg.status != "PENDING"
    assert msg.status != "FAILED"


@pytest.mark.asyncio
async def test_stale_dispatcher_a_dispatch_is_rejected_when_b_holds_claim(hf_env, db):
    """
    BUG-02: If Dispatcher A attempts to commit DISPATCHED after Dispatcher B
    has claimed the row with a new token, Dispatcher A's update affects 0 rows.
    """
    run_id = str(uuid4())
    msg = create_outbox_message(db, "SCRAPE_RUN_DISPATCH", {"run_id": run_id})
    db.commit()

    dispatcher_a = OutboxDispatcher()
    dispatcher_b = OutboxDispatcher()

    # 1. Dispatcher A claims
    claimed_a = dispatcher_a.claim_next_message(db, lease_seconds=1)
    token_a = claimed_a.claim_token

    # 2. Lease expires
    claimed_a.claimed_until = datetime.now(timezone.utc) - timedelta(seconds=5)
    db.commit()

    # 3. Dispatcher B claims (replaces token with token_b)
    claimed_b = dispatcher_b.claim_next_message(db, lease_seconds=60)
    token_b = claimed_b.claim_token
    assert token_b != token_a

    # 4. Dispatcher A attempts to dispatch with stale token_a
    stale_msg_a = OutboxMessage(
        id=msg.id,
        event_type="SCRAPE_RUN_DISPATCH",
        payload={"run_id": run_id},
        status="CLAIMED",
        claim_token=token_a,
        attempts=1
    )
    mock_pool_a = AsyncMock()
    mock_pool_a.enqueue_job = AsyncMock(return_value=MagicMock(job_id=f"scrape_{run_id}"))
    success_a = await dispatcher_a.dispatch_claimed_message(db, stale_msg_a, pool=mock_pool_a)
    assert success_a is False # Rejected by conditional update!

    # 5. Row is still CLAIMED by Dispatcher B
    db.expire_all()
    reloaded_msg = db.query(OutboxMessage).filter(OutboxMessage.id == msg.id).first()
    assert reloaded_msg.status == "CLAIMED"
    assert reloaded_msg.claim_token == token_b


def test_two_dispatchers_claim_distinct_messages_with_unique_tokens(hf_env, db):
    """
    BUG-02: Two concurrent dispatchers claim distinct messages,
    each receiving distinct unique claim tokens.
    """
    msgs = [create_outbox_message(db, "SCRAPE_RUN_DISPATCH", {"run_id": f"tok_{i}"}) for i in range(2)]
    db.commit()

    d1 = OutboxDispatcher()
    d2 = OutboxDispatcher()

    c1 = d1.claim_next_message(db)
    c2 = d2.claim_next_message(db)

    assert c1 is not None and c2 is not None
    assert c1.id != c2.id
    assert c1.claim_token is not None
    assert c2.claim_token is not None
    assert c1.claim_token != c2.claim_token


# ===========================================================================
# MULTI-SESSION REGRESSION TESTS FOR OUTBOX CLAIM FENCING (TOCTOU)
# ===========================================================================

@pytest.mark.asyncio
async def test_success_race_stale_dispatcher_updates_zero_rows_and_claim_intact(hf_env, db):
    """
    Regression Test (Success Race):
    1. Dispatcher A claims the message (lease_seconds=1).
    2. Lease expires.
    3. Dispatcher B claims the message with a new token in a separate session.
    4. Dispatcher A attempts the success update with its stale token in its own session.
    5. Verify Dispatcher A's update returns False (0 rows updated), and Dispatcher B's claim remains intact.
    """
    conn = db.connection()
    session_a = TestingSessionLocal(bind=conn)
    session_b = TestingSessionLocal(bind=conn)

    try:
        run_id = str(uuid4())
        msg = create_outbox_message(session_a, "SCRAPE_RUN_DISPATCH", {"run_id": run_id})
        session_a.commit()
        msg_id = msg.id

        dispatcher_a = OutboxDispatcher()
        dispatcher_b = OutboxDispatcher()

        # 1. Dispatcher A claims
        claimed_a = dispatcher_a.claim_next_message(session_a, lease_seconds=1)
        assert claimed_a is not None
        token_a = claimed_a.claim_token
        assert token_a is not None

        # 2. Lease expires
        claimed_a.claimed_until = datetime.now(timezone.utc) - timedelta(seconds=5)
        session_a.commit()

        # 3. Dispatcher B claims in separate session
        claimed_b = dispatcher_b.claim_next_message(session_b, lease_seconds=60)
        assert claimed_b is not None
        assert claimed_b.id == msg_id
        token_b = claimed_b.claim_token
        assert token_b != token_a

        # 4. Dispatcher A attempts success update with stale token_a
        stale_msg_a = OutboxMessage(
            id=msg_id,
            event_type="SCRAPE_RUN_DISPATCH",
            payload={"run_id": run_id},
            status="CLAIMED",
            claim_token=token_a,
            attempts=1
        )
        mock_pool = AsyncMock()
        mock_pool.enqueue_job = AsyncMock(return_value=MagicMock(job_id=f"scrape_{run_id}"))

        success_a = await dispatcher_a.dispatch_claimed_message(session_a, stale_msg_a, pool=mock_pool)
        assert success_a is False

        # 5. Verify Dispatcher B's claim remains intact in DB
        session_b.expire_all()
        reloaded = session_b.query(OutboxMessage).filter(OutboxMessage.id == msg_id).first()
        assert reloaded.status == "CLAIMED"
        assert reloaded.claim_token == token_b
        assert reloaded.dispatched_at is None
    finally:
        session_a.close()
        session_b.close()


@pytest.mark.asyncio
async def test_failure_race_stale_dispatcher_updates_zero_rows_and_claim_intact(hf_env, db):
    """
    Regression Test (Failure Race):
    1. Dispatcher A claims the message, lease expires.
    2. Dispatcher B claims the message with a new token in a separate session.
    3. Dispatcher A attempts the failure update with its stale token in its own session.
    4. Verify Dispatcher A returns False (0 rows updated), and Dispatcher B's claim remains intact.
    """
    conn = db.connection()
    session_a = TestingSessionLocal(bind=conn)
    session_b = TestingSessionLocal(bind=conn)

    try:
        run_id = str(uuid4())
        msg = create_outbox_message(session_a, "SCRAPE_RUN_DISPATCH", {"run_id": run_id})
        session_a.commit()
        msg_id = msg.id

        dispatcher_a = OutboxDispatcher()
        dispatcher_b = OutboxDispatcher()

        # 1. Dispatcher A claims
        claimed_a = dispatcher_a.claim_next_message(session_a, lease_seconds=1)
        assert claimed_a is not None
        token_a = claimed_a.claim_token

        # 2. Lease expires
        claimed_a.claimed_until = datetime.now(timezone.utc) - timedelta(seconds=5)
        session_a.commit()

        # 3. Dispatcher B claims in separate session
        claimed_b = dispatcher_b.claim_next_message(session_b, lease_seconds=60)
        assert claimed_b is not None
        token_b = claimed_b.claim_token
        assert token_b != token_a

        # 4. Dispatcher A attempts failure update with stale token_a
        stale_msg_a = OutboxMessage(
            id=msg_id,
            event_type="SCRAPE_RUN_DISPATCH",
            payload={"run_id": run_id},
            status="CLAIMED",
            claim_token=token_a,
            attempts=1
        )
        now = datetime.now(timezone.utc)
        exc = Exception("Worker A timeout error")
        res_a = dispatcher_a._handle_failure(session_a, stale_msg_a, exc, now, claim_token=token_a)
        assert res_a is False

        # 5. Verify Dispatcher B's claim remains intact
        session_b.expire_all()
        reloaded = session_b.query(OutboxMessage).filter(OutboxMessage.id == msg_id).first()
        assert reloaded.status == "CLAIMED"
        assert reloaded.claim_token == token_b
        assert reloaded.attempts == 0
        assert reloaded.error_message is None
    finally:
        session_a.close()
        session_b.close()


@pytest.mark.asyncio
async def test_valid_current_token_marks_message_dispatched(hf_env, db):
    """
    Verifies that a dispatcher holding the valid current token can successfully
    mark the message DISPATCHED and atomically clear claim fields.
    """
    run_id = str(uuid4())
    msg = create_outbox_message(db, "SCRAPE_RUN_DISPATCH", {"run_id": run_id})
    db.commit()

    dispatcher = OutboxDispatcher()
    claimed = dispatcher.claim_next_message(db, lease_seconds=60)
    assert claimed is not None
    token = claimed.claim_token
    assert token is not None

    mock_pool = AsyncMock()
    mock_pool.enqueue_job = AsyncMock(return_value=MagicMock(job_id=f"scrape_{run_id}"))

    success = await dispatcher.dispatch_claimed_message(db, claimed, pool=mock_pool)
    assert success is True

    db.expire_all()
    reloaded = db.query(OutboxMessage).filter(OutboxMessage.id == msg.id).first()
    assert reloaded.status == "DISPATCHED"
    assert reloaded.dispatched_at is not None
    assert reloaded.claim_token is None
    assert reloaded.claimed_until is None
    assert reloaded.error_message is None


@pytest.mark.asyncio
async def test_valid_current_token_triggers_retry_handling(hf_env, db):
    """
    Verifies that a dispatcher holding the valid current token can trigger retry handling,
    transitioning message to PENDING with exponential backoff and error details.
    """
    run_id = str(uuid4())
    msg = create_outbox_message(db, "SCRAPE_RUN_DISPATCH", {"run_id": run_id})
    db.commit()

    dispatcher = OutboxDispatcher()
    claimed = dispatcher.claim_next_message(db, lease_seconds=60)
    assert claimed is not None
    token = claimed.claim_token

    now = datetime.now(timezone.utc)
    exc = Exception("Redis temporary unreachable")
    res = dispatcher._handle_failure(db, claimed, exc, now, claim_token=token)
    assert res is False

    db.expire_all()
    reloaded = db.query(OutboxMessage).filter(OutboxMessage.id == msg.id).first()
    assert reloaded.status == "PENDING"
    assert reloaded.attempts == 1
    assert reloaded.error_message == "Redis temporary unreachable"
    assert reloaded.claim_token is None
    assert reloaded.claimed_until is None
    assert reloaded.next_attempt_at is not None
    next_attempt = reloaded.next_attempt_at if reloaded.next_attempt_at.tzinfo else reloaded.next_attempt_at.replace(tzinfo=timezone.utc)
    assert next_attempt > now


@pytest.mark.asyncio
async def test_terminal_dispatched_message_cannot_regress_to_pending_or_failed(hf_env, db):
    """
    Verifies that once a message reaches DISPATCHED, any stale failure update
    is rejected and cannot cause the message to regress to PENDING or FAILED.
    """
    run_id = str(uuid4())
    msg = create_outbox_message(db, "SCRAPE_RUN_DISPATCH", {"run_id": run_id})
    db.commit()

    dispatcher = OutboxDispatcher()
    claimed = dispatcher.claim_next_message(db, lease_seconds=60)
    token = claimed.claim_token

    mock_pool = AsyncMock()
    mock_pool.enqueue_job = AsyncMock(return_value=MagicMock(job_id=f"scrape_{run_id}"))
    success = await dispatcher.dispatch_claimed_message(db, claimed, pool=mock_pool)
    assert success is True

    db.expire_all()
    dispatched_msg = db.query(OutboxMessage).filter(OutboxMessage.id == msg.id).first()
    assert dispatched_msg.status == "DISPATCHED"
    orig_dispatched_at = dispatched_msg.dispatched_at

    # Stale attempt with stale token tries to report failure
    stale_msg = OutboxMessage(
        id=msg.id,
        event_type="SCRAPE_RUN_DISPATCH",
        payload={"run_id": run_id},
        status="CLAIMED",
        claim_token=token,
        attempts=1
    )
    now = datetime.now(timezone.utc)
    res = dispatcher._handle_failure(db, stale_msg, Exception("Late failure"), now, claim_token=token)
    assert res is False

    # Message must remain DISPATCHED
    db.expire_all()
    reloaded = db.query(OutboxMessage).filter(OutboxMessage.id == msg.id).first()
    assert reloaded.status == "DISPATCHED"
    assert reloaded.dispatched_at == orig_dispatched_at
    assert reloaded.error_message is None


@pytest.mark.asyncio
async def test_stale_token_cannot_modify_retry_or_error_fields(hf_env, db):
    """
    Verifies that a stale dispatcher cannot modify attempts, error_message,
    or next_attempt_at on a record held by an active claim.
    """
    conn = db.connection()
    session_a = TestingSessionLocal(bind=conn)
    session_b = TestingSessionLocal(bind=conn)

    try:
        run_id = str(uuid4())
        msg = create_outbox_message(session_a, "SCRAPE_RUN_DISPATCH", {"run_id": run_id})
        session_a.commit()
        msg_id = msg.id

        dispatcher_a = OutboxDispatcher()
        dispatcher_b = OutboxDispatcher()

        # Dispatcher A claims then lease expires
        c_a = dispatcher_a.claim_next_message(session_a, lease_seconds=1)
        token_a = c_a.claim_token
        c_a.claimed_until = datetime.now(timezone.utc) - timedelta(seconds=5)
        session_a.commit()

        # Dispatcher B claims
        c_b = dispatcher_b.claim_next_message(session_b, lease_seconds=60)
        token_b = c_b.claim_token
        assert token_b != token_a

        # Stale Dispatcher A attempts failure update
        stale_msg_a = OutboxMessage(
            id=msg_id,
            event_type="SCRAPE_RUN_DISPATCH",
            payload={"run_id": run_id},
            status="CLAIMED",
            claim_token=token_a,
            attempts=3
        )
        now = datetime.now(timezone.utc)
        res = dispatcher_a._handle_failure(session_a, stale_msg_a, Exception("Stale err"), now, claim_token=token_a)
        assert res is False

        # Verify in session_b that none of A's error/attempt values touched the row
        session_b.expire_all()
        current = session_b.query(OutboxMessage).filter(OutboxMessage.id == msg_id).first()
        assert current.status == "CLAIMED"
        assert current.claim_token == token_b
        assert current.attempts == 0
        assert current.error_message is None
    finally:
        session_a.close()
        session_b.close()
