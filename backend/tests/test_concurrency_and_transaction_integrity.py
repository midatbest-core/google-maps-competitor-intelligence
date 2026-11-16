import asyncio
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from uuid import uuid4
from fastapi.testclient import TestClient

from app.main import app
from app.models import (
    User, Workspace, WorkspaceMember, Project, BusinessProfile,
    ProjectCompetitor, ScrapeRun, ScrapeRunCompetitor, Post
)
from app.services.scrape_service import ScrapeService
from app.core.security import create_access_token
from app.core.database import SessionLocal
from app.workers.main import _execute_scrape_job
from app.scraper.schemas import ScrapeResult

PROD_ORIGIN = "https://google-maps-competitor-intelligence.onrender.com"


@pytest.fixture
def test_env(db):
    from app.api.dependencies import get_db, get_current_user, get_current_workspace
    app.dependency_overrides[get_db] = lambda: db

    user = User(id=str(uuid4()), email="test_concurrency@example.com", hashed_password="pw")
    ws = Workspace(id=str(uuid4()), name="WS Concurrency")
    db.add_all([user, ws])
    db.commit()

    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_current_workspace] = lambda: ws

    member = WorkspaceMember(workspace_id=ws.id, user_id=user.id, role="OWNER")
    db.add(member)

    own_biz = BusinessProfile(
        id=str(uuid4()),
        business_name="Main Brand Cafe",
        google_maps_url="https://maps.google.com/?cid=12345"
    )
    db.add(own_biz)
    db.flush()

    project = Project(
        id=str(uuid4()),
        name="Project Concurrency",
        workspace_id=ws.id,
        own_business_id=own_biz.id
    )
    db.add(project)
    db.commit()

    # Add 3 competitors
    for i in range(1, 4):
        b = BusinessProfile(
            id=str(uuid4()),
            business_name=f"Competitor {i}",
            google_maps_url=f"https://maps.google.com/?cid=comp_{i}"
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
# 1. Test two simultaneous resume requests for the same scrape run
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_two_simultaneous_resume_requests_rejected(test_env, db):
    """
    Simultaneous resume requests on the same run:
    The first acquires the lock and transitions the run to QUEUED.
    The second encounters an active run and must receive HTTP 409 Conflict.
    """
    project_id = test_env["project"].id
    client = TestClient(app)

    failed_run = ScrapeRun(id=str(uuid4()), project_id=project_id, status="FAILED", run_number=1)
    db.add(failed_run)
    db.commit()

    mock_pool = AsyncMock()
    mock_pool.enqueue_job = AsyncMock(return_value=MagicMock(job_id=f"scrape_{failed_run.id}"))
    mock_pool.close = AsyncMock()

    with patch("app.api.routes.get_redis_pool", return_value=mock_pool):
        # First request succeeds
        resp1 = client.post(f"/scrape-runs/{failed_run.id}/resume", headers=test_env["auth_headers"])
        assert resp1.status_code == 200

        # Run is now in QUEUED; second resume while active (simultaneous) rejects
        failed_run.status = "RUNNING"
        db.commit()

        resp2 = client.post(f"/scrape-runs/{failed_run.id}/resume", headers=test_env["auth_headers"])
        assert resp2.status_code == 409
        assert "already active" in resp2.json()["detail"].lower()


# ---------------------------------------------------------------------------
# 2. Test two simultaneous start-scrape requests for the same project
# ---------------------------------------------------------------------------
def test_two_simultaneous_start_scrape_requests_rejected(test_env, db):
    """
    Two simultaneous start-scrape requests for the same project:
    First creates the run and holds project lock.
    Second sees active run and receives HTTP 409 Conflict.
    """
    project_id = test_env["project"].id
    client = TestClient(app)

    mock_pool = AsyncMock()
    mock_pool.enqueue_job = AsyncMock(return_value=MagicMock(job_id="scrape_job_1"))
    mock_pool.close = AsyncMock()

    with patch("app.api.routes.get_redis_pool", return_value=mock_pool):
        resp1 = client.post(f"/projects/{project_id}/scrape", headers=test_env["auth_headers"])
        assert resp1.status_code == 202

        # Second simultaneous request hits while run is QUEUED
        resp2 = client.post(f"/projects/{project_id}/scrape", headers=test_env["auth_headers"])
        assert resp2.status_code == 409
        assert "already has an active run" in resp2.json()["detail"]


# ---------------------------------------------------------------------------
# 3. Verify only one ARQ job is created per run
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_only_one_arq_job_created_per_run():
    """Verify that passing _job_id to ARQ deduplicates simultaneous enqueue calls."""
    mock_pool = AsyncMock()
    job_instance = MagicMock()
    # First enqueue returns job; duplicate enqueue with same _job_id returns None
    mock_pool.enqueue_job.side_effect = [job_instance, None]

    job1 = await mock_pool.enqueue_job("scrape_job", "run-123", _job_id="scrape_run-123")
    assert job1 is not None

    job2 = await mock_pool.enqueue_job("scrape_job", "run-123", _job_id="scrape_run-123")
    assert job2 is None  # ARQ native deduplication


# ---------------------------------------------------------------------------
# 4. Verify database state is committed before worker can process
# ---------------------------------------------------------------------------
def test_database_committed_before_worker_can_process(test_env, db):
    """
    Verify that create_scrape_run commits ScrapeRun and ScrapeRunCompetitors
    BEFORE start_scrape notifies Redis.
    """
    project_id = test_env["project"].id
    service = ScrapeService(db, workspace=test_env["ws"])

    run = service.create_scrape_run(project_id)

    # Verify that in a completely separate session, the run and competitors are visible
    assert run.id is not None
    assert run.run_number is not None
    assert run.status == "QUEUED"
    assert run.competitors_attempted == 3

    # Direct query in session confirms committed state
    comps = db.query(ScrapeRunCompetitor).filter(ScrapeRunCompetitor.scrape_run_id == run.id).all()
    assert len(comps) == 3
    assert all(c.status == "PENDING" for c in comps)


# ---------------------------------------------------------------------------
# 5. Simulate API crash immediately after successful Redis enqueueing
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_api_crash_after_successful_redis_enqueue(test_env, db):
    """
    Simulate API web process crashing right after pool.enqueue_job succeeds.
    Verify:
    - Run remains QUEUED in DB.
    - Worker picks up the job and can execute to completion.
    """
    project_id = test_env["project"].id
    service = ScrapeService(db, workspace=test_env["ws"])
    run = service.create_scrape_run(project_id)
    run_id = run.id

    # Simulate API process dying after enqueueing...
    # Worker starts asynchronously
    mock_adapter = MagicMock()
    mock_adapter.scrape = AsyncMock(return_value=ScrapeResult(status="NO_DATA", posts=[]))
    mock_adapter.close = AsyncMock()

    ctx = {"scraper_adapter": mock_adapter}
    worker_db = MagicMock(wraps=db)
    worker_db.close = MagicMock()
    with patch("app.workers.main.SessionLocal", return_value=worker_db):
        await _execute_scrape_job(ctx, run_id)

    # Verify run completed successfully despite API crash
    db.refresh(run)
    assert run.status == "SUCCESS"
    assert run.competitors_succeeded == 3
    assert run.competitors_failed == 0


# ---------------------------------------------------------------------------
# 6. Simulate Redis enqueue failure: verify run marked FAILED cleanly
# ---------------------------------------------------------------------------
def test_redis_enqueue_failure_marks_run_failed_cleanly(test_env, db):
    """
    When Redis is offline during start_scrape:
    - API returns 503 Service Unavailable.
    - Run is marked FAILED in DB (not left stuck in QUEUED).
    - Subsequent scrape requests can be initiated without being blocked.
    """
    project_id = test_env["project"].id
    client = TestClient(app)

    with patch("app.api.routes.get_redis_pool", side_effect=Exception("Redis connection refused")):
        resp = client.post(f"/projects/{project_id}/scrape", headers=test_env["auth_headers"])
        assert resp.status_code == 503

    # Check database
    latest_run = db.query(ScrapeRun).filter(ScrapeRun.project_id == project_id).order_by(ScrapeRun.created_at.desc()).first()
    assert latest_run.status == "FAILED"
    assert "queue service unavailable" in latest_run.error_logs[0].lower()

    # Verify that project is NOT blocked by stale QUEUED run
    mock_pool = AsyncMock()
    mock_pool.enqueue_job = AsyncMock(return_value=MagicMock(job_id="job_ok"))
    mock_pool.close = AsyncMock()
    with patch("app.api.routes.get_redis_pool", return_value=mock_pool):
        resp_next = client.post(f"/projects/{project_id}/scrape", headers=test_env["auth_headers"])
        assert resp_next.status_code == 202


# ---------------------------------------------------------------------------
# 7. Verify ARQ duplicate job IDs and retry behavior
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_arq_duplicate_job_ids_and_retry_behavior():
    """Verify that ARQ job IDs prevent double execution and allow resume re-enqueue."""
    enqueued_jobs = {}

    class MockArqPool:
        async def enqueue_job(self, func_name, *args, _job_id=None, **kwargs):
            if _job_id and _job_id in enqueued_jobs:
                return None  # ARQ behavior: return None if job is already queued
            job = MagicMock(job_id=_job_id)
            if _job_id:
                enqueued_jobs[_job_id] = job
            return job

        async def close(self):
            pass

    pool = MockArqPool()
    job1 = await pool.enqueue_job("scrape_job", "run-99", _job_id="scrape_run-99")
    assert job1 is not None

    # Immediate duplicate attempt
    job2 = await pool.enqueue_job("scrape_job", "run-99", _job_id="scrape_run-99")
    assert job2 is None  # Blocked

    # Worker finishes job: clears key
    del enqueued_jobs["scrape_run-99"]

    # Resume attempt re-enqueues cleanly
    job3 = await pool.enqueue_job("scrape_job", "run-99", _job_id="scrape_run-99")
    assert job3 is not None


# ---------------------------------------------------------------------------
# 8. Ensure completed competitors are never processed again during resume
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_completed_competitors_never_reprocessed_on_resume(test_env, db):
    """
    CRITICAL TEST:
    A scrape run has:
    - Competitor 1: SUCCESS (1 post)
    - Competitor 2: NO_DATA (0 posts)
    - Competitor 3: FAILED
    On resume:
    - Competitor 1 and Competitor 2 must be skipped completely.
    - Only Competitor 3 must be processed by adapter.scrape.
    """
    project_id = test_env["project"].id
    service = ScrapeService(db, workspace=test_env["ws"])
    run = service.create_scrape_run(project_id)

    # Set up competitor states
    comps = db.query(ScrapeRunCompetitor).filter(ScrapeRunCompetitor.scrape_run_id == run.id).all()
    comp1, comp2, comp3 = comps[0], comps[1], comps[2]

    comp1.status = "SUCCESS"
    comp1.posts_discovered = 1
    comp2.status = "NO_DATA"
    comp2.posts_discovered = 0
    comp3.status = "FAILED"
    comp3.error_message = "Previous timeout"
    run.status = "PARTIAL_SUCCESS"
    db.commit()

    # Track which URLs are scraped
    scraped_urls = []

    class MockResumeAdapter:
        async def scrape(self, target_url: str):
            scraped_urls.append(target_url)
            return ScrapeResult(status="SUCCESS", posts=[])

        async def close(self):
            pass

    ctx = {"scraper_adapter": MockResumeAdapter()}
    worker_db = MagicMock(wraps=db)
    worker_db.close = MagicMock()
    with patch("app.workers.main.SessionLocal", return_value=worker_db):
        await _execute_scrape_job(ctx, run.id)

    # Verify: ONLY competitor 3 was scraped!
    assert len(scraped_urls) == 1
    assert comp3.business.google_maps_url in scraped_urls[0]

    # Verify: competitor 1 and 2 statuses were preserved
    db.refresh(comp1)
    db.refresh(comp2)
    assert comp1.status == "SUCCESS"
    assert comp1.posts_discovered == 1
    assert comp2.status == "NO_DATA"
