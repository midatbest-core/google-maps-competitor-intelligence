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
    
    # 2. unauthenticated user cannot start scrape
    app.dependency_overrides.clear()
    unauth_res = client.post(f"/projects/{proj_id}/scrape")
    assert unauth_res.status_code == 401
    
    # Restore overrides for other tests
    app.dependency_overrides[get_current_workspace] = override_get_current_workspace
    app.dependency_overrides[get_current_user] = override_get_current_user

def test_scrape_schedule_api():
    create_res = client.post("/projects", json={"name": "Schedule Project"})
    proj_id = create_res.json()["id"]

    get_res = client.get(f"/projects/{proj_id}/scrape-schedule")
    assert get_res.status_code == 404

    put_res = client.put(
        f"/projects/{proj_id}/scrape-schedule",
        json={
            "enabled": True,
            "frequency": "DAILY",
            "time_of_day": "09:00",
            "timezone": "UTC"
        }
    )
    assert put_res.status_code == 200
    assert put_res.json()["enabled"] is True
    assert put_res.json()["next_run_at"] is not None

    get_res2 = client.get(f"/projects/{proj_id}/scrape-schedule")
    assert get_res2.status_code == 200
    assert get_res2.json()["time_of_day"] == "09:00"

    dis_res = client.put(
        f"/projects/{proj_id}/scrape-schedule",
        json={
            "enabled": False,
            "frequency": "DAILY",
            "time_of_day": "09:00",
            "timezone": "UTC"
        }
    )
    assert dis_res.status_code == 200
    assert dis_res.json()["enabled"] is False
    assert dis_res.json()["next_run_at"] is None

    inv_res = client.put(
        f"/projects/{proj_id}/scrape-schedule",
        json={
            "enabled": True,
            "frequency": "DAILY",
            "time_of_day": "25:00",
            "timezone": "UTC"
        }
    )
    assert inv_res.status_code == 422

    inv_tz = client.put(
        f"/projects/{proj_id}/scrape-schedule",
        json={
            "enabled": True,
            "frequency": "DAILY",
            "time_of_day": "09:00",
            "timezone": "Invalid/Zone"
        }
    )
    assert inv_tz.status_code == 422

    app.dependency_overrides[get_current_workspace] = lambda: mock_workspace_2
    for_res = client.get(f"/projects/{proj_id}/scrape-schedule")
    assert for_res.status_code == 404
    
    app.dependency_overrides[get_current_workspace] = override_get_current_workspace

@pytest.mark.asyncio
async def test_scheduler_tick():
    from app.workers.main import scheduler_tick
    create_res = client.post("/projects", json={"name": "Tick Project"})
    proj_id = create_res.json()["id"]

    client.put(
        f"/projects/{proj_id}/scrape-schedule",
        json={
            "enabled": True,
            "frequency": "DAILY",
            "time_of_day": "00:00",
            "timezone": "UTC"
        }
    )
    
    from app.core.database import SessionLocal
    from app.models.scrape import ScrapeSchedule
    db = SessionLocal()
    schedule = db.query(ScrapeSchedule).filter(ScrapeSchedule.project_id == proj_id).first()
    from datetime import datetime, timezone, timedelta
    schedule.next_run_at = datetime.now(timezone.utc) - timedelta(hours=1)
    db.commit()
    db.close()

    await scheduler_tick(None)

    runs_res = client.get(f"/projects/{proj_id}/scrape-runs")
    assert runs_res.status_code == 200
    assert len(runs_res.json()) == 1
    
    get_res = client.get(f"/projects/{proj_id}/scrape-schedule")
    assert get_res.json()["next_run_at"] is not None
    next_run_str = get_res.json()["next_run_at"].replace("Z", "+00:00")
    if "+" not in next_run_str and "-" not in next_run_str[10:]: # basic check for tz info
        next_run_str += "+00:00"
    next_run = datetime.fromisoformat(next_run_str).replace(tzinfo=timezone.utc)
    assert next_run > datetime.now(timezone.utc)
    
    db = SessionLocal()
    schedule = db.query(ScrapeSchedule).filter(ScrapeSchedule.project_id == proj_id).first()
    schedule.next_run_at = datetime.now(timezone.utc) - timedelta(hours=1)
    db.commit()
    db.close()
    
    await scheduler_tick(None)
    runs_res2 = client.get(f"/projects/{proj_id}/scrape-runs")
    assert len(runs_res2.json()) == 1

@pytest.mark.asyncio
async def test_scheduler_tick_concurrency():
    from app.workers.main import scheduler_tick
    create_res = client.post("/projects", json={"name": "Tick Concurrency Project"})
    proj_id = create_res.json()["id"]

    client.put(
        f"/projects/{proj_id}/scrape-schedule",
        json={
            "enabled": True,
            "frequency": "DAILY",
            "time_of_day": "00:00",
            "timezone": "UTC"
        }
    )
    
    from app.core.database import SessionLocal
    from app.models.scrape import ScrapeSchedule
    db = SessionLocal()
    schedule = db.query(ScrapeSchedule).filter(ScrapeSchedule.project_id == proj_id).first()
    from datetime import datetime, timezone, timedelta
    schedule.next_run_at = datetime.now(timezone.utc) - timedelta(hours=1)
    db.commit()
    db.close()

    import asyncio
    await asyncio.gather(
        scheduler_tick(None),
        scheduler_tick(None)
    )

    runs_res = client.get(f"/projects/{proj_id}/scrape-runs")
    assert runs_res.status_code == 200
    assert len(runs_res.json()) == 1 # Exactly one run created!
    
    get_res = client.get(f"/projects/{proj_id}/scrape-schedule")
    next_run_str = get_res.json()["next_run_at"].replace("Z", "+00:00")
    if "+" not in next_run_str and "-" not in next_run_str[10:]: 
        next_run_str += "+00:00"
    next_run = datetime.fromisoformat(next_run_str).replace(tzinfo=timezone.utc)
    
    assert next_run > datetime.now(timezone.utc)
