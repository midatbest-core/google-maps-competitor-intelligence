import pytest
from datetime import datetime, timezone
from fastapi.testclient import TestClient

from app.main import app
from app.core.database import get_db
from app.models.profile import BusinessProfile
from app.models.project import Project
from app.models.competitor import ProjectCompetitor
from app.models.post import Post
from app.models.review import Review
from app.models.scrape import ScrapeRun, ScrapeRunCompetitor
from app.models.analysis import AIAnalysis, IntelligenceReport
from app.models.auth import User, Workspace, WorkspaceMember
from app.scraper.schemas import ScrapeResult, NormalizedPost, ReviewScrapeResult, ExtractedReview
from app.workers.main import scrape_job, combined_intelligence_job
from app.api.dependencies import get_current_user, get_current_workspace

@pytest.mark.asyncio
async def test_posts_and_reviews_independent_e2e_pipeline(db):
    # Setup test workspace and user
    user = User(id="e2e_user", email="e2e@test.com", hashed_password="pw", is_active=True)
    ws = Workspace(id="e2e_ws", name="E2E Workspace")
    db.add_all([user, ws])
    db.commit()

    member = WorkspaceMember(workspace_id=ws.id, user_id=user.id, role="OWNER")
    db.add(member)

    # Setup businesses: Own Business & Competitor
    own_biz = BusinessProfile(
        business_name="Our Specialty Bakery",
        google_maps_url="https://maps.google.com/?cid=own1",
        category="Bakery"
    )
    comp_biz = BusinessProfile(
        business_name="Mega Chain Bakery",
        google_maps_url="https://maps.google.com/?cid=comp1",
        category="Bakery"
    )
    db.add_all([own_biz, comp_biz])
    db.commit()

    project = Project(
        name="Bakery Intelligence Q4",
        workspace_id=ws.id,
        own_business_id=own_biz.id
    )
    db.add(project)
    db.commit()

    comp = ProjectCompetitor(
        project_id=project.id,
        business_id=comp_biz.id,
        is_active=True
    )
    db.add(comp)
    db.commit()

    # Create ScrapeRun
    scrape_run = ScrapeRun(project_id=project.id, status="QUEUED")
    db.add(scrape_run)
    db.commit()

    c_run = ScrapeRunCompetitor(
        scrape_run_id=scrape_run.id,
        business_id=comp_biz.id,
        status="PENDING"
    )
    db.add(c_run)
    db.commit()

    # Mock Post Scraper Adapter
    class MockPostAdapter:
        async def scrape(self, target_url: str):
            res = ScrapeResult(status="SUCCESS")
            res.posts = [
                NormalizedPost(
                    source_id="post_1",
                    text_content="Try our fresh chocolate croissants baked every 30 minutes! Special 20% off coupon today.",
                    cta_text="Order now",
                    cta_url="https://order.com",
                    published_date=datetime.now(timezone.utc),
                    fingerprint="post_fp_croissant"
                ),
                NormalizedPost(
                    source_id="post_2",
                    text_content="Excited to announce our weekend sourdough workshops!",
                    published_date=datetime.now(timezone.utc),
                    fingerprint="post_fp_sourdough"
                )
            ]
            return res

        async def close(self):
            pass

    # Mock Review Scraper
    class MockReviewScraper:
        async def scrape_reviews(self, target_url: str, max_reviews: int = 25):
            res = ReviewScrapeResult(status="SUCCESS")
            res.reviews = [
                ExtractedReview(
                    source_id="rev_1",
                    author_name="Karen D.",
                    rating=1.0,
                    text="Waited 30 minutes in line and they were completely sold out of croissants! Disorganized staff.",
                    relative_time_description="Yesterday",
                    source="browser_scraper",
                    fingerprint="rev_fp_sold_out"
                ),
                ExtractedReview(
                    source_id="rev_2",
                    author_name="David L.",
                    rating=5.0,
                    text="The sourdough bread is world class when you can get it.",
                    relative_time_description="3 days ago",
                    source="browser_scraper",
                    fingerprint="rev_fp_sourdough_good"
                )
            ]
            return res

        async def close(self):
            pass

    # Execute scrape_job with mock context
    ctx = {
        "scraper_adapter": MockPostAdapter()
    }

    # Patch the ReviewCollectorService to use our MockReviewScraper and SessionLocal to use test db
    from unittest.mock import patch

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

    with patch("app.services.review_collector.GoogleMapsReviewScraper", return_value=MockReviewScraper()), \
         patch("app.workers.main.SessionLocal", side_effect=lambda: NonClosingSession(db)):
        await scrape_job(ctx, scrape_run.id)

    db.refresh(scrape_run)
    db.refresh(c_run)

    # 1. Verify Run Status
    assert scrape_run.status == "SUCCESS"
    assert c_run.status == "SUCCESS"
    assert c_run.posts_discovered == 2
    assert c_run.new_posts == 2

    # 2. Verify Posts Persistence & Competitor Association
    stored_posts = db.query(Post).filter_by(business_id=comp_biz.id).all()
    assert len(stored_posts) == 2
    croissant_post = next(p for p in stored_posts if "croissants" in p.text_content)
    assert croissant_post.fingerprint == "post_fp_croissant"

    # 3. Verify Reviews Persistence & Competitor Association
    stored_reviews = db.query(Review).filter_by(business_id=comp_biz.id).all()
    assert len(stored_reviews) == 2
    complaint_rev = next(r for r in stored_reviews if r.rating == 1.0)
    assert "Waited 30 minutes" in complaint_rev.text
    assert complaint_rev.source == "browser_scraper"
    assert complaint_rev.sentiment == "NEGATIVE"

    # 4. Trigger Combined Intelligence
    with patch("app.workers.main.SessionLocal", side_effect=lambda: NonClosingSession(db)):
        await combined_intelligence_job(None, project.id)

    latest_report = db.query(IntelligenceReport).filter_by(project_id=project.id).first()
    assert latest_report is not None
    assert latest_report.status == "COMPLETED"
    assert latest_report.posts_analyzed == 2
    assert latest_report.reviews_analyzed == 2
    assert len(latest_report.strategic_disconnects) > 0
    assert len(latest_report.actionable_recommendations) > 0
    assert len(latest_report.content_ideas) > 0

    # 5. Verify API Retrieval
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_current_workspace] = lambda: ws

    client = TestClient(app)

    # Test GET Posts API
    p_resp = client.get(f"/projects/{project.id}/posts")
    assert p_resp.status_code == 200
    p_data = p_resp.json()
    assert p_data["total"] == 2

    # Test GET Reviews API
    r_resp = client.get(f"/projects/{project.id}/reviews")
    assert r_resp.status_code == 200
    r_data = r_resp.json()
    assert r_data["total"] == 2
    assert r_data["items"][0]["business_name"] == "Mega Chain Bakery"

    # Test GET Intelligence API
    i_resp = client.get(f"/projects/{project.id}/intelligence")
    assert i_resp.status_code == 200
    i_data = i_resp.json()
    assert i_data["id"] == latest_report.id
    assert i_data["posts_analyzed"] == 2
    assert i_data["reviews_analyzed"] == 2

    # Clean overrides
    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(get_current_workspace, None)
