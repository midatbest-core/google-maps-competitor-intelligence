import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from uuid import uuid4
from fastapi.testclient import TestClient

from app.main import app
from app.models import (
    User, Workspace, WorkspaceMember, Project, BusinessProfile,
    ProjectCompetitor, ScrapeRun, ScrapeRunCompetitor
)
from app.services.scrape_service import ScrapeService
from app.core.security import create_access_token

PROD_ORIGIN = "https://google-maps-competitor-intelligence.onrender.com"


@pytest.fixture
def test_setup(db):
    from app.api.dependencies import get_db, get_current_user, get_current_workspace
    app.dependency_overrides[get_db] = lambda: db

    user = User(id=str(uuid4()), email="test_cors@example.com", hashed_password="pw")
    ws = Workspace(id=str(uuid4()), name="WS CORS")
    db.add_all([user, ws])
    db.commit()

    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_current_workspace] = lambda: ws

    member = WorkspaceMember(workspace_id=ws.id, user_id=user.id, role="OWNER")
    db.add(member)

    # Primary business profile
    own_biz = BusinessProfile(
        id=str(uuid4()),
        business_name="My Cafe",
        google_maps_url="https://maps.google.com/?cid=111111"
    )
    db.add(own_biz)
    db.flush()

    project = Project(
        id=str(uuid4()),
        name="Project CORS",
        workspace_id=ws.id,
        own_business_id=own_biz.id
    )
    db.add(project)
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


def test_cors_options_preflight_on_scrape_endpoints(test_setup):
    client = TestClient(app)
    project_id = test_setup["project"].id

    # 1. OPTIONS preflight on /projects/{project_id}/scrape-runs
    resp1 = client.options(
        f"/projects/{project_id}/scrape-runs",
        headers={
            "Origin": PROD_ORIGIN,
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "authorization,content-type"
        }
    )
    assert resp1.status_code == 200
    assert resp1.headers.get("access-control-allow-origin") == PROD_ORIGIN
    assert resp1.headers.get("access-control-allow-credentials") == "true"
    assert "GET" in resp1.headers.get("access-control-allow-methods", "")

    # 2. OPTIONS preflight on /scrape-runs/{fake_id}
    resp2 = client.options(
        f"/scrape-runs/{str(uuid4())}",
        headers={
            "Origin": PROD_ORIGIN,
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "authorization"
        }
    )
    assert resp2.status_code == 200
    assert resp2.headers.get("access-control-allow-origin") == PROD_ORIGIN
    assert resp2.headers.get("access-control-allow-credentials") == "true"


def test_cors_headers_on_authenticated_and_error_responses(test_setup, db):
    from app.api.dependencies import get_current_user, get_current_workspace
    client = TestClient(app)
    project_id = test_setup["project"].id

    # 1. Unauthenticated request (401) should still carry CORS headers
    user_override = app.dependency_overrides.pop(get_current_user, None)
    ws_override = app.dependency_overrides.pop(get_current_workspace, None)
    try:
        resp_401 = client.get(
            f"/projects/{project_id}/scrape-runs",
            headers={"Origin": PROD_ORIGIN}
        )
        assert resp_401.status_code == 401
        assert resp_401.headers.get("access-control-allow-origin") == PROD_ORIGIN
    finally:
        if user_override:
            app.dependency_overrides[get_current_user] = user_override
        if ws_override:
            app.dependency_overrides[get_current_workspace] = ws_override

    # 2. Nonexistent resource (404) should carry CORS headers
    resp_404 = client.get(
        f"/scrape-runs/{str(uuid4())}",
        headers=test_setup["auth_headers"]
    )
    assert resp_404.status_code == 404
    assert resp_404.headers.get("access-control-allow-origin") == PROD_ORIGIN

    # 3. Successful GET (200) carries CORS headers
    resp_200 = client.get(
        f"/projects/{project_id}/scrape-runs",
        headers=test_setup["auth_headers"]
    )
    assert resp_200.status_code == 200
    assert resp_200.headers.get("access-control-allow-origin") == PROD_ORIGIN


def test_cors_never_wildcards_when_credentials_true():
    """Ensure allow_origins does not contain wildcard '*' alongside credentials."""
    from app.core.config import settings
    assert "*" not in settings.CORS_ORIGINS
    assert PROD_ORIGIN in settings.CORS_ORIGINS


def test_roster_selection_includes_all_40_eligible_competitors(test_setup, db):
    """
    ISSUE 2 VERIFICATION:
    Ensure that when a project has 40 active competitors, create_scrape_run
    accurately adds all 40 to the scrape run without truncation.
    """
    project = test_setup["project"]
    ws = test_setup["ws"]

    # Create 40 distinct competitors
    competitors = []
    for i in range(40):
        b = BusinessProfile(
            id=str(uuid4()),
            business_name=f"Roster Competitor {i+1}",
            google_maps_url=f"https://maps.google.com/?cid=test_cid_{i+1}",
            category="Cafe"
        )
        db.add(b)
        db.flush()
        pc = ProjectCompetitor(
            project_id=project.id,
            business_id=b.id,
            is_active=True
        )
        db.add(pc)
        competitors.append(pc)
    db.commit()

    service = ScrapeService(db, workspace=ws)
    run = service.create_scrape_run(project.id)

    assert run.competitors_attempted == 40
    # Check database persistence
    run_comps = db.query(ScrapeRunCompetitor).filter(ScrapeRunCompetitor.scrape_run_id == run.id).all()
    assert len(run_comps) == 40
    assert all(rc.status == "PENDING" for rc in run_comps)


def test_roster_selection_excludes_inactive_competitors(test_setup, db):
    """Verify that competitors marked is_active=False are excluded from the scrape run."""
    project = test_setup["project"]
    ws = test_setup["ws"]

    # 5 active and 3 inactive
    for i in range(5):
        b = BusinessProfile(id=str(uuid4()), business_name=f"Active {i}", google_maps_url=f"https://maps.google.com/?cid=act_{i}")
        db.add(b)
        db.flush()
        db.add(ProjectCompetitor(project_id=project.id, business_id=b.id, is_active=True))

    for i in range(3):
        b = BusinessProfile(id=str(uuid4()), business_name=f"Inactive {i}", google_maps_url=f"https://maps.google.com/?cid=inact_{i}")
        db.add(b)
        db.flush()
        db.add(ProjectCompetitor(project_id=project.id, business_id=b.id, is_active=False))
    db.commit()

    service = ScrapeService(db, workspace=ws)
    run = service.create_scrape_run(project.id)
    assert run.competitors_attempted == 5


@pytest.mark.asyncio
async def test_start_scrape_enqueues_to_redis_pool():
    """Verify start_scrape enqueues to Redis ARQ pool and avoids web process execution."""
    client = TestClient(app)

    mock_pool = AsyncMock()
    mock_pool.enqueue_job = AsyncMock()
    mock_pool.close = AsyncMock()

    with patch("app.api.routes.get_redis_pool", return_value=mock_pool):
        mock_run = MagicMock()
        mock_run.id = "test-run-123"
        mock_run.run_number = 1
        mock_run.display_name = "Scrape 001"
        mock_run.project_id = "test-proj-123"
        mock_run.status = "QUEUED"
        mock_run.competitors_attempted = 10
        mock_run.competitors_succeeded = 0
        mock_run.competitors_failed = 0
        mock_run.start_time = None
        mock_run.end_time = None
        mock_run.error_logs = []
        mock_run.competitor_runs = []

        mock_service = MagicMock()
        mock_service.create_scrape_run.return_value = mock_run

        from app.api.dependencies import get_scrape_service
        app.dependency_overrides[get_scrape_service] = lambda: mock_service

        try:
            resp = client.post(
                "/projects/test-proj-123/scrape",
                headers={"Authorization": "Bearer fake_token", "Origin": PROD_ORIGIN}
            )
            assert resp.status_code == 202
            mock_pool.enqueue_job.assert_awaited_once_with("scrape_job", "test-run-123", _job_id="scrape_test-run-123")
        finally:
            app.dependency_overrides.pop(get_scrape_service, None)


@pytest.mark.asyncio
async def test_start_scrape_returns_503_when_redis_unavailable(test_setup, db):
    """
    CRITICAL REQUIREMENT 1 & 3:
    When Redis is unavailable, start_scrape MUST return 503 Service Unavailable,
    must NOT fall back to in-process execution, and MUST mark run as FAILED so
    it does not remain permanently stuck in QUEUED.
    """
    client = TestClient(app)
    project_id = test_setup["project"].id

    with patch("app.api.routes.get_redis_pool", side_effect=Exception("Redis connection refused")):
        resp = client.post(
            f"/projects/{project_id}/scrape",
            headers=test_setup["auth_headers"]
        )
        assert resp.status_code == 503
        assert "queue service is unavailable" in resp.json()["detail"].lower()
        # Verify CORS header is still present on 503 response
        assert resp.headers.get("access-control-allow-origin") == PROD_ORIGIN

    # Verify database state: run was marked FAILED, not left in QUEUED
    latest_run = db.query(ScrapeRun).filter(ScrapeRun.project_id == project_id).order_by(ScrapeRun.created_at.desc()).first()
    assert latest_run is not None
    assert latest_run.status == "FAILED"
    assert "queue service unavailable" in latest_run.error_logs[0].lower()


def test_duplicate_scrape_request_rejected_409(test_setup, db):
    """CRITICAL REQUIREMENT 4: Prevent duplicate scrape runs for an active project."""
    project_id = test_setup["project"].id

    # Create an active run
    active_run = ScrapeRun(project_id=project_id, status="RUNNING", run_number=1)
    db.add(active_run)
    db.commit()

    client = TestClient(app)
    resp = client.post(
        f"/projects/{project_id}/scrape",
        headers=test_setup["auth_headers"]
    )
    assert resp.status_code == 409
    assert "already has an active run" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_resume_scrape_run_enqueues_to_redis_and_rejects_active(test_setup, db):
    """Verify resume_scrape_run enqueues to Redis and rejects active runs with 409."""
    project_id = test_setup["project"].id
    client = TestClient(app)

    # 1. Run that is failed/interrupted can be resumed
    failed_run = ScrapeRun(id=str(uuid4()), project_id=project_id, status="FAILED", run_number=1)
    db.add(failed_run)
    db.commit()

    mock_pool = AsyncMock()
    mock_pool.enqueue_job = AsyncMock()
    mock_pool.close = AsyncMock()

    with patch("app.api.routes.get_redis_pool", return_value=mock_pool):
        resp = client.post(
            f"/scrape-runs/{failed_run.id}/resume",
            headers=test_setup["auth_headers"]
        )
        assert resp.status_code == 200
        mock_pool.enqueue_job.assert_awaited_once_with("scrape_job", failed_run.id, _job_id=f"scrape_{failed_run.id}")

    # 2. Duplicate resume on already active run rejects with 409
    active_run = ScrapeRun(id=str(uuid4()), project_id=project_id, status="RUNNING", run_number=2)
    db.add(active_run)
    db.commit()

    resp_dup = client.post(
        f"/scrape-runs/{active_run.id}/resume",
        headers=test_setup["auth_headers"]
    )
    assert resp_dup.status_code == 409
    assert "already active" in resp_dup.json()["detail"]


def test_api_routes_never_import_scrape_job_directly():
    """
    CRITICAL REQUIREMENT 5:
    Verify that backend/app/api/routes.py source code never imports scrape_job or executes
    Chromium scraping directly.
    """
    import inspect
    import app.api.routes as routes_module
    source = inspect.getsource(routes_module)
    assert "from app.workers.main import scrape_job" not in source
    assert "import scrape_job" not in source
    assert "background_tasks.add_task(scrape_job" not in source

