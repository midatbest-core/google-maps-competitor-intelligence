import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.models.auth import Workspace, User
from app.api.dependencies import get_current_workspace, get_current_user
from app.core.database import engine
from app.models.base import Base

client = TestClient(app)

mock_workspace = Workspace(id="ws_1", name="WS 1")
mock_workspace_2 = Workspace(id="ws_2", name="WS 2")
mock_user = User(id="usr_1", email="test@test.com", is_active=True)

def override_get_current_workspace():
    return mock_workspace

def override_get_current_user():
    return mock_user

app.dependency_overrides[get_current_workspace] = override_get_current_workspace
app.dependency_overrides[get_current_user] = override_get_current_user

# Mock redis pool to avoid side effects
import app.api.routes as routes
class MockRedisPool:
    async def enqueue_job(self, *args, **kwargs):
        pass
    async def close(self):
        pass
    async def ping(self):
        pass

async def mock_get_redis_pool():
    return MockRedisPool()
routes.get_redis_pool = mock_get_redis_pool

@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)

def test_scrape_api_authorization():
    global mock_workspace

    # 1. authenticated user can start scrape for own project
    create_res = client.post("/projects", json={"name": "Scrape Project"})
    assert create_res.status_code == 201
    proj_id = create_res.json()["id"]

    start_res = client.post(f"/projects/{proj_id}/scrape")
    assert start_res.status_code == 202
    run_id = start_res.json()["id"]

    # 4. own project can list scrape runs
    list_res = client.get(f"/projects/{proj_id}/scrape-runs")
    assert list_res.status_code == 200
    assert len(list_res.json()) == 1

    # 6. own run can be retrieved
    get_res = client.get(f"/scrape-runs/{run_id}")
    assert get_res.status_code == 200
    assert get_res.json()["id"] == run_id

    # 8. own paused run can be resumed
    resume_res = client.post(f"/scrape-runs/{run_id}/resume")
    assert resume_res.status_code == 200

    # Switch to foreign workspace
    app.dependency_overrides[get_current_workspace] = lambda: mock_workspace_2

    # 3. foreign workspace cannot start scrape
    start_res_for = client.post(f"/projects/{proj_id}/scrape")
    assert start_res_for.status_code == 404 # Depends on project validation, usually raises ValueError -> 404

    # 5. foreign project cannot list scrape runs
    list_res_for = client.get(f"/projects/{proj_id}/scrape-runs")
    assert list_res_for.status_code == 404

    # 7. foreign run cannot be retrieved
    get_res_for = client.get(f"/scrape-runs/{run_id}")
    assert get_res_for.status_code == 404 # or 403 based on implementation

    # 9. foreign run cannot be resumed
    resume_res_for = client.post(f"/scrape-runs/{run_id}/resume")
    assert resume_res_for.status_code == 404

    # 10. invalid/nonexistent run handled correctly
    invalid_res = client.get("/scrape-runs/nonexistent-run-id")
    assert invalid_res.status_code == 404

    # Reset workspace
    app.dependency_overrides[get_current_workspace] = override_get_current_workspace

    # 2. unauthenticated user cannot start scrape on someone else's project
    app.dependency_overrides.clear()
    unauth_res = client.post(f"/projects/{proj_id}/scrape")
    assert unauth_res.status_code == 404

    # Restore overrides for other tests
    app.dependency_overrides[get_current_workspace] = override_get_current_workspace
    app.dependency_overrides[get_current_user] = override_get_current_user

def test_delete_scrape_run():
    # Create project
    create_res = client.post("/projects", json={"name": "Delete Run Test Project"})
    proj_id = create_res.json()["id"]

    # Add run
    start_res = client.post(f"/projects/{proj_id}/scrape")
    run_id = start_res.json()["id"]

    # Delete run
    del_res = client.delete(f"/projects/{proj_id}/scrape-runs/{run_id}")
    assert del_res.status_code == 204

    # Run should not be found
    get_res = client.get(f"/scrape-runs/{run_id}")
    assert get_res.status_code == 404

    # Deleting again returns 404
    del_res2 = client.delete(f"/projects/{proj_id}/scrape-runs/{run_id}")
    assert del_res2.status_code == 404
