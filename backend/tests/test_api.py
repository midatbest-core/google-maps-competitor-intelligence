import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.models.scrape import ScrapeRun, ScrapeRunCompetitor
from app.workers.main import scrape_job
from app.core.database import get_db, SessionLocal
from app.scraper.schemas import ScrapeResult, NormalizedPost
import app.api.routes as routes

client = TestClient(app)

from app.api.dependencies import get_current_workspace, get_current_user
from app.models.auth import Workspace, User

def override_get_current_user():
    return User(id="test_user", email="test@test.com", hashed_password="pw", is_active=True)

def override_get_current_workspace():
    return Workspace(id="test_ws", name="Test Workspace")

app.dependency_overrides[get_current_user] = override_get_current_user
app.dependency_overrides[get_current_workspace] = override_get_current_workspace

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

async def mock_scrape_job(*args, **kwargs):
    pass
routes.scrape_job = mock_scrape_job
import app.api.discovery as discovery
discovery.scrape_job = mock_scrape_job

from app.core.database import engine
from app.models.base import Base
# Make sure models are registered
from app.models.project import Project
from app.models.profile import BusinessProfile
from app.models.competitor import ProjectCompetitor
from app.models.post import Post
from app.models.scrape import ScrapeRun, ScrapeRunCompetitor, ScrapeObservation

@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)

def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

@pytest.mark.asyncio
async def test_project_lifecycle():
    # 1. Create project
    response = client.post("/projects", json={"name": "Integration Test Project"})
    assert response.status_code == 201
    project_id = response.json()["id"]

    # 2. Get projects
    response = client.get("/projects")
    assert response.status_code == 200
    assert len(response.json()) > 0

    # 3. Add Competitors
    # C1: SUCCESS
    c1_res = client.post(f"/projects/{project_id}/competitors", json={"business_name": "Standard Biz", "google_maps_url": "http://g.co/1"})
    assert c1_res.status_code == 201
    
    # C2: VERIFICATION_REQUIRED
    c2_res = client.post(f"/projects/{project_id}/competitors", json={"business_name": "Require Captcha Biz", "google_maps_url": "http://g.co/2"})
    assert c2_res.status_code == 201

    # C3: FAILED
    c3_res = client.post(f"/projects/{project_id}/competitors", json={"business_name": "Error Network Biz", "google_maps_url": "http://g.co/3"})
    assert c3_res.status_code == 201

    # C4: NO DATA
    c4_res = client.post(f"/projects/{project_id}/competitors", json={"business_name": "No_Data Biz", "google_maps_url": "http://g.co/4"})
    assert c4_res.status_code == 201

    # 4. Clear auto-triggered runs from discovery
    runs = client.get(f"/projects/{project_id}/scrape-runs").json()
    for r in runs:
        client.delete(f"/projects/{project_id}/scrape-runs/{r['id']}")

    # Start Scrape manually now that all 4 competitors exist
    scrape_res = client.post(f"/projects/{project_id}/scrape")
    assert scrape_res.status_code == 202
    run_id = scrape_res.json()["id"]

    # 5. Run mock worker job synchronously
    class MockAdapter:
        async def scrape(self, target_url: str):
            res = ScrapeResult()
            if "1" in target_url:
                res.status = "SUCCESS"
                res.posts = [NormalizedPost(source_id="p1", fingerprint="f1")] * 5
            elif "2" in target_url:
                res.status = "VERIFICATION_REQUIRED"
                res.error_message = "Mocked CAPTCHA"
            elif "3" in target_url:
                res.status = "FAILED"
                res.error_message = "Mocked Network Error"
            else:
                res.status = "NO_DATA"
            return res
        async def close(self): pass

    ctx = {'scraper_adapter': MockAdapter()}
    await scrape_job(ctx, run_id)

    # 6. Verify run state
    run_res = client.get(f"/scrape-runs/{run_id}")
    run_data = run_res.json()
    assert run_data["status"] == "PAUSED_MANUAL_INTERVENTION"
    assert run_data["competitors_attempted"] == 4
    assert run_data["competitors_succeeded"] == 2
    assert run_data["competitors_failed"] == 1

    # 7. Resume
    resume_res = client.post(f"/scrape-runs/{run_id}/resume")
    assert resume_res.status_code == 200
    assert resume_res.json()["status"] == "QUEUED"

