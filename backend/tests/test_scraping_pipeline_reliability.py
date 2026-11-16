import asyncio
from datetime import datetime, timezone
import pytest
from uuid import uuid4
from unittest.mock import MagicMock, patch

from app.models import (
    User, Workspace, WorkspaceMember, Project, BusinessProfile,
    ProjectCompetitor, ScrapeRun, ScrapeRunCompetitor, Post
)
from app.scraper.schemas import ScrapeResult, NormalizedPost
from app.workers.main import scrape_job
from app.services.scrape_service import ScrapeService


@pytest.mark.asyncio
async def test_sequential_run_numbering(db):
    """Verify that scrape runs receive sequential run_number (1, 2, 3...) per project."""
    user = User(id=str(uuid4()), email="test_seq@example.com", hashed_password="pw")
    ws = Workspace(id=str(uuid4()), name="WS Seq")
    db.add_all([user, ws])
    db.commit()

    member = WorkspaceMember(workspace_id=ws.id, user_id=user.id, role="OWNER")
    db.add(member)
    project = Project(id=str(uuid4()), name="Project Seq", workspace_id=ws.id)
    db.add(project)
    db.commit()

    service = ScrapeService(db, workspace=ws)

    # Create run 1
    run1 = service.create_scrape_run(project.id)
    assert run1.run_number == 1
    assert run1.display_name == "Scrape 001"
    run1.status = "SUCCESS"
    db.commit()

    # Create run 2
    run2 = service.create_scrape_run(project.id)
    assert run2.run_number == 2
    assert run2.display_name == "Scrape 002"
    run2.status = "SUCCESS"
    db.commit()

    # Create run 3
    run3 = service.create_scrape_run(project.id)
    assert run3.run_number == 3
    assert run3.display_name == "Scrape 003"
    run3.status = "SUCCESS"
    db.commit()

    # Verify retrieval
    runs = service.get_runs_for_project(project.id)
    assert len(runs) == 3
    assert [r.run_number for r in runs] == [3, 2, 1] or [r.run_number for r in runs] == [1, 2, 3]


@pytest.mark.asyncio
async def test_third_business_failure_does_not_block_subsequent_businesses(db):
    """
    CRITICAL TEST: Verify that when the third business times out or fails,
    subsequent businesses (4th, 5th) continue to be processed and the run
    completes with PARTIAL_SUCCESS rather than getting stuck.
    """
    user = User(id=str(uuid4()), email="test_biz3@example.com", hashed_password="pw")
    ws = Workspace(id=str(uuid4()), name="WS Biz3")
    db.add_all([user, ws])
    db.commit()

    member = WorkspaceMember(workspace_id=ws.id, user_id=user.id, role="OWNER")
    db.add(member)
    project = Project(id=str(uuid4()), name="Project Biz3", workspace_id=ws.id)
    db.add(project)
    db.commit()

    # Create 5 businesses
    businesses = []
    for i in range(1, 6):
        b = BusinessProfile(
            business_name=f"Bakery {i}",
            google_maps_url=f"https://maps.google.com/?cid=test_cid_{i}",
            category="Bakery"
        )
        db.add(b)
        db.flush()
        comp = ProjectCompetitor(project_id=project.id, business_id=b.id, is_active=True)
        db.add(comp)
        businesses.append(b)
    db.commit()

    service = ScrapeService(db, workspace=ws)
    run = service.create_scrape_run(project.id)
    assert run.competitors_attempted == 5
    run_id = run.id

    # Mock adapter where business 3 times out or fails, but 1, 2, 4, 5 succeed
    call_log = []

    class MockFlakyAdapter:
        async def scrape(self, target_url: str):
            call_log.append(target_url)
            res = ScrapeResult()
            if "cid_3" in target_url:
                # Business 3 fails with timeout or error
                res.status = "ERROR"
                res.error_message = "Simulated navigation timeout on business 3"
            elif "cid_1" in target_url or "cid_2" in target_url:
                res.status = "SUCCESS"
                res.posts = [
                    NormalizedPost(
                        source_id=f"p_{target_url}",
                        text_content=f"Post for {target_url}",
                        fingerprint=f"fp_{target_url}"
                    )
                ]
            else:
                res.status = "NO_DATA"
            return res

        async def close(self):
            pass

    ctx = {"scraper_adapter": MockFlakyAdapter()}

    class NonClosingSession:
        def __init__(self, session):
            self._session = session
        def __enter__(self):
            return self
        def __exit__(self, exc_type, exc_val, exc_tb):
            pass
        def close(self):
            pass
        def __getattr__(self, item):
            return getattr(self._session, item)

    with patch("app.workers.main.SessionLocal", side_effect=lambda: NonClosingSession(db)):
        await scrape_job(ctx, run_id)

    db.refresh(run)
    comp_runs = db.query(ScrapeRunCompetitor).filter(ScrapeRunCompetitor.scrape_run_id == run_id).all()

    # 1. Verify ALL 5 businesses were processed (none was skipped or blocked)
    assert len(comp_runs) == 5
    assert len(call_log) == 5, f"Expected 5 scrapes, but only {len(call_log)} were called: {call_log}"

    # 2. Check individual statuses
    b3_run = next(c for c in comp_runs if c.business.google_maps_url.endswith("cid_3"))
    assert b3_run.status == "ERROR"
    assert "timeout" in b3_run.error_message.lower()

    b4_run = next(c for c in comp_runs if c.business.google_maps_url.endswith("cid_4"))
    assert b4_run.status == "NO_DATA"

    b5_run = next(c for c in comp_runs if c.business.google_maps_url.endswith("cid_5"))
    assert b5_run.status == "NO_DATA"

    # 3. Overall run status must be PARTIAL_SUCCESS (not FAILED or stuck in RUNNING)
    assert run.status == "PARTIAL_SUCCESS"
    assert run.competitors_succeeded == 4  # 1, 2, 4, 5
    assert run.competitors_failed == 1     # 3
    assert run.end_time is not None


@pytest.mark.asyncio
async def test_scrape_job_per_business_timeout_isolation(db):
    """Verify that an indefinite hang in a single business triggers timeout and continues."""
    user = User(id=str(uuid4()), email="test_timeout@example.com", hashed_password="pw")
    ws = Workspace(id=str(uuid4()), name="WS Timeout")
    db.add_all([user, ws])
    db.commit()

    member = WorkspaceMember(workspace_id=ws.id, user_id=user.id, role="OWNER")
    db.add(member)
    project = Project(id=str(uuid4()), name="Project Timeout", workspace_id=ws.id)
    db.add(project)
    db.commit()

    for i in range(1, 4):
        b = BusinessProfile(business_name=f"Timeout Biz {i}", google_maps_url=f"https://maps.google.com/?cid=time_{i}")
        db.add(b)
        db.flush()
        db.add(ProjectCompetitor(project_id=project.id, business_id=b.id, is_active=True))
    db.commit()

    service = ScrapeService(db, workspace=ws)
    run = service.create_scrape_run(project.id)

    class HangingAdapter:
        async def scrape(self, target_url: str):
            if "time_2" in target_url:
                # Hang intentionally
                await asyncio.sleep(100)
            res = ScrapeResult(status="SUCCESS")
            res.posts = [NormalizedPost(source_id=f"p_{target_url}", text_content="OK", fingerprint=f"fp_{target_url}")]
            return res
        async def close(self): pass

    ctx = {"scraper_adapter": HangingAdapter()}

    class NonClosingSession:
        def __init__(self, session): self._session = session
        def __enter__(self): return self
        def __exit__(self, exc_type, exc_val, exc_tb): pass
        def close(self): pass
        def __getattr__(self, item): return getattr(self._session, item)

    # Patch PER_BUSINESS_TIMEOUT to 0.1s for fast deterministic test execution
    with patch("app.workers.main.SessionLocal", side_effect=lambda: NonClosingSession(db)), \
         patch("app.workers.main.PER_BUSINESS_TIMEOUT", 0.1):
        await scrape_job(ctx, run.id)

    db.refresh(run)
    comp_runs = db.query(ScrapeRunCompetitor).filter(ScrapeRunCompetitor.scrape_run_id == run.id).all()

    # Business 2 should have timed out, but Business 3 must be SUCCESS
    b2_run = next(c for c in comp_runs if "time_2" in c.business.google_maps_url)
    assert b2_run.status == "ERROR"
    assert "timeout" in b2_run.error_message.lower()

    b3_run = next(c for c in comp_runs if "time_3" in c.business.google_maps_url)
    assert b3_run.status == "SUCCESS"
    assert run.status == "PARTIAL_SUCCESS"
