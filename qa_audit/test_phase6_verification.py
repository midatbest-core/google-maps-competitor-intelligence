import os
import sys
import time
from uuid import uuid4

# Ensure backend in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.models.base import Base
from app.models.auth import User, Workspace, WorkspaceMember
from app.models.project import Project
from app.models.profile import BusinessProfile
from app.models.competitor import ProjectCompetitor
from app.models.scrape import ScrapeRun, ScrapeRunCompetitor
from app.repositories.scrape_repo import ScrapeRunRepository
from app.repositories.project_repo import ProjectRepository
from app.services.scrape_service import ScrapeService
from app.api.routes import scrape_router, project_router
from app.api.dependencies import get_current_user, get_current_workspace

from sqlalchemy.pool import StaticPool

# Setup test DB
engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
    echo=False
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base.metadata.create_all(bind=engine)

def test_scrape_service_batch_performance():
    """Verify that creating a scrape run with 60 competitors executes quickly using batch add."""
    db = TestingSessionLocal()
    try:
        user = User(id=str(uuid4()), email="test@example.com", hashed_password="pw")
        db.add(user)
        workspace = Workspace(id=str(uuid4()), name="Test WS")
        db.add(workspace)
        project = Project(id=str(uuid4()), name="Test Project", workspace_id=workspace.id)
        db.add(project)
        db.commit()

        # Add 60 competitors to project
        for i in range(60):
            biz = BusinessProfile(
                id=str(uuid4()),
                business_name=f"Competitor {i}",
                canonical_source_id=f"place_{i}"
            )
            db.add(biz)
            db.flush()
            comp = ProjectCompetitor(
                id=str(uuid4()),
                project_id=project.id,
                business_id=biz.id
            )
            db.add(comp)
        db.commit()

        service = ScrapeService(db, workspace=workspace)

        t0 = time.perf_counter()
        run = service.create_scrape_run(project_id=project.id)
        t_duration = time.perf_counter() - t0

        assert run is not None
        assert run.status == "QUEUED"
        assert run.competitors_attempted == 60
        assert len(run.competitor_runs) == 60
        print(f"[PERF] 60 competitors scrape run created & flushed in {t_duration * 1000:.2f}ms")
        assert t_duration < 1.0, f"Run creation took too long: {t_duration}s"

    finally:
        db.close()


def test_eager_loading_scrape_repo():
    """Verify that ScrapeRunRepository.get eagerly loads competitor_runs and their businesses."""
    db = TestingSessionLocal()
    try:
        workspace = Workspace(id=str(uuid4()), name="WS 2")
        db.add(workspace)
        project = Project(id=str(uuid4()), name="Project 2", workspace_id=workspace.id)
        db.add(project)
        biz = BusinessProfile(id=str(uuid4()), business_name="Biz 1", canonical_source_id="p1")
        db.add(biz)
        db.commit()

        run = ScrapeRun(id=str(uuid4()), project_id=project.id, status="QUEUED")
        db.add(run)
        db.commit()

        comp_run = ScrapeRunCompetitor(id=str(uuid4()), scrape_run_id=run.id, business_id=biz.id)
        db.add(comp_run)
        db.commit()

        # Expire all cached objects in session
        db.expire_all()

        repo = ScrapeRunRepository(db)
        fetched_run = repo.get(run.id)

        assert fetched_run is not None
        assert len(fetched_run.competitor_runs) == 1
        assert fetched_run.competitor_runs[0].business.business_name == "Biz 1"

        # Also verify get_runs_for_project
        db.expire_all()
        project_runs = repo.get_runs_for_project(project.id)
        assert len(project_runs) == 1
        assert len(project_runs[0].competitor_runs) == 1
        assert project_runs[0].competitor_runs[0].business.business_name == "Biz 1"
        print("[VERIFIED] Eager loading on ScrapeRun and get_runs_for_project verified.")

    finally:
        db.close()


def test_active_run_conflict_returns_409():
    """Verify that attempting to create a scrape run when one is already active returns 409 Conflict."""
    db = TestingSessionLocal()
    app = FastAPI()
    app.include_router(project_router)
    app.include_router(scrape_router)

    workspace = Workspace(id=str(uuid4()), name="WS 409")
    db.add(workspace)
    user = User(id=str(uuid4()), email="test409@example.com", hashed_password="pw")
    db.add(user)
    member = WorkspaceMember(id=str(uuid4()), workspace_id=workspace.id, user_id=user.id, role="OWNER")
    db.add(member)
    project = Project(id=str(uuid4()), name="Project 409", workspace_id=workspace.id)
    db.add(project)
    
    # Active run created right now (not stale)
    active_run = ScrapeRun(id=str(uuid4()), project_id=project.id, status="QUEUED")
    db.add(active_run)
    db.commit()

    def get_test_db():
        try:
            yield db
        finally:
            pass

    def get_test_user():
        return user

    from app.core.database import get_db
    app.dependency_overrides[get_db] = get_test_db
    app.dependency_overrides[get_current_user] = get_test_user
    app.dependency_overrides[get_current_workspace] = lambda: workspace

    client = TestClient(app)
    response = client.post(f"/projects/{project.id}/scrape")
    assert response.status_code == 409, f"Expected 409 Conflict, got {response.status_code}: {response.text}"
    assert "already has an active run" in response.json()["detail"].lower()
    print("[VERIFIED] Active run conflict maps to HTTP 409 Conflict.")


if __name__ == "__main__":
    test_scrape_service_batch_performance()
    test_eager_loading_scrape_repo()
    test_active_run_conflict_returns_409()
    print("\nAll Phase 6 Python verification checks passed successfully!")
