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
from app.models.analysis import AIAnalysis, IntelligenceReport
from app.models.auth import User, Workspace, WorkspaceMember
from app.scraper.schemas import ExtractedReview
from app.services.review_ingestion_service import ReviewIngestionService
from app.services.combined_intelligence_service import CombinedIntelligenceService
from app.providers.ai.fake import FakeAIProvider
from app.api.dependencies import get_current_user, get_current_workspace

def test_review_ingestion_and_deduplication(db):
    biz = BusinessProfile(
        business_name="Test Cafe",
        google_maps_url="https://maps.google.com/?cid=1001",
        category="Cafe"
    )
    db.add(biz)
    db.commit()

    service = ReviewIngestionService(db)

    rev_data = ExtractedReview(
        author_name="Alice Smith",
        rating=5.0,
        text="The espresso and croissants were delicious! Best in town.",
        relative_time_description="2 days ago",
        source="browser_scraper"
    )

    res1 = service.ingest_review(biz.id, rev_data)
    assert res1.status == "NEW_REVIEW"
    assert res1.review_id is not None

    stored = db.query(Review).filter_by(id=res1.review_id).first()
    assert stored is not None
    assert stored.author_name == "Alice Smith"
    assert stored.rating == 5.0
    assert stored.sentiment == "POSITIVE"
    assert stored.source == "browser_scraper"

    # Ingest second time (exact duplicate) -> should be deduplicated
    res2 = service.ingest_review(biz.id, rev_data)
    assert res2.status == "DUPLICATE"
    assert res2.review_id == res1.review_id

    count = db.query(Review).filter_by(business_id=biz.id).count()
    assert count == 1


@pytest.mark.asyncio
async def test_combined_intelligence_synthesis(db):
    user = User(email="architect@example.com", hashed_password="hashedpassword123")
    ws = Workspace(name="Intelligence Workspace")
    db.add_all([user, ws])
    db.commit()

    member = WorkspaceMember(workspace_id=ws.id, user_id=user.id, role="OWNER")
    db.add(member)

    own_biz = BusinessProfile(business_name="Apex Bistro", category="Restaurant")
    comp_biz = BusinessProfile(business_name="Competitor Central", category="Restaurant")
    db.add_all([own_biz, comp_biz])
    db.commit()

    project = Project(
        name="Apex Intelligence Project",
        workspace_id=ws.id,
        own_business_id=own_biz.id
    )
    db.add(project)
    db.commit()

    comp_link = ProjectCompetitor(project_id=project.id, business_id=comp_biz.id, is_active=True)
    db.add(comp_link)
    db.commit()

    # Add competitor post promoting weekend live music
    post = Post(
        business_id=comp_biz.id,
        text_content="Join us every Saturday for live acoustic sessions and cocktails!",
        fingerprint="live_music_post_fp_1",
        scraped_date=datetime.now(timezone.utc)
    )
    db.add(post)
    db.commit()

    post_analysis = AIAnalysis(
        post_id=post.id,
        provider="fake",
        model_name="fake_model",
        topic="Weekend Live Music",
        content_type="event",
        cta_type="Visit us",
        offer_or_promotion="Live music",
        sentiment="positive"
    )
    db.add(post_analysis)

    # Add competitor review complaining of weekend wait times
    review = Review(
        business_id=comp_biz.id,
        author_name="Frustrated Diner",
        rating=2.0,
        text="Waited 45 minutes for a table even with reservations. Extremely loud and orders took forever.",
        sentiment="NEGATIVE",
        source="browser_scraper",
        fingerprint="rev_wait_time_fp_1"
    )
    db.add(review)
    db.commit()

    ai_provider = FakeAIProvider()
    intel_service = CombinedIntelligenceService(db, ai_provider, workspace=ws)

    report = await intel_service.generate_report(project.id)
    assert report.status == "COMPLETED"
    assert report.posts_analyzed >= 1
    assert report.reviews_analyzed >= 1
    assert report.competitor_insights is not None
    assert len(report.competitor_insights) > 0
    assert report.strategic_disconnects is not None
    assert len(report.strategic_disconnects) > 0

    disconnect = report.strategic_disconnects[0]
    assert "advertised_promise" in disconnect
    assert "customer_reality" in disconnect
    assert "opportunity" in disconnect

    recommendations = report.actionable_recommendations
    assert recommendations is not None
    assert len(recommendations) > 0
    assert "supporting_evidence" in recommendations[0]

    content_ideas = report.content_ideas
    assert content_ideas is not None
    assert len(content_ideas) > 0

    latest = intel_service.get_latest_report(project.id)
    assert latest is not None
    assert latest.id == report.id


def test_reviews_api_endpoints(db):
    user = User(id="user_rev_1", email="testreviews@example.com", hashed_password="hashedpassword123")
    ws = Workspace(id="ws_rev_1", name="Reviews API Workspace")
    db.add_all([user, ws])
    db.commit()

    member = WorkspaceMember(workspace_id=ws.id, user_id=user.id, role="OWNER")
    db.add(member)
    db.commit()

    biz = BusinessProfile(business_name="Downtown Diner", category="Diner")
    db.add(biz)
    db.commit()

    project = Project(name="Diner Project", workspace_id=ws.id, own_business_id=biz.id)
    db.add(project)
    db.commit()

    comp_biz = BusinessProfile(business_name="Burger Shack", category="Fast Food")
    db.add(comp_biz)
    db.commit()
    comp = ProjectCompetitor(project_id=project.id, business_id=comp_biz.id, is_active=True)
    db.add(comp)
    db.commit()

    r1 = Review(
        business_id=comp_biz.id,
        author_name="Bob",
        rating=4.0,
        text="Great burgers, fries were a bit cold.",
        sentiment="POSITIVE",
        source="browser_scraper",
        fingerprint="bob_fp_1"
    )
    r2 = Review(
        business_id=comp_biz.id,
        author_name="Charlie",
        rating=1.0,
        text="Rude staff and dirty tables.",
        sentiment="NEGATIVE",
        source="google_places_api",
        fingerprint="charlie_fp_2"
    )
    db.add_all([r1, r2])
    db.commit()

    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_current_workspace] = lambda: ws

    client = TestClient(app)

    # Test GET /projects/{project_id}/reviews
    resp = client.get(f"/projects/{project.id}/reviews")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2
    assert len(data["items"]) == 2
    assert data["items"][0]["business_name"] == "Burger Shack"

    # Test GET with sentiment filter
    resp_neg = client.get(f"/projects/{project.id}/reviews?sentiment=NEGATIVE")
    assert resp_neg.status_code == 200
    assert resp_neg.json()["total"] == 1
    assert resp_neg.json()["items"][0]["author_name"] == "Charlie"

    # Test GET with source filter
    resp_src = client.get(f"/projects/{project.id}/reviews?source=google_places_api")
    assert resp_src.status_code == 200
    assert resp_src.json()["total"] == 1
    assert resp_src.json()["items"][0]["source"] == "google_places_api"

    # Test POST /projects/{project_id}/intelligence/analyze
    resp_intel = client.post(f"/projects/{project.id}/intelligence/analyze")
    assert resp_intel.status_code == 200
    intel_data = resp_intel.json()
    assert intel_data["status"] == "COMPLETED"
    assert len(intel_data["strategic_disconnects"]) > 0

    # Test GET /projects/{project_id}/intelligence
    resp_latest = client.get(f"/projects/{project.id}/intelligence")
    assert resp_latest.status_code == 200
    assert resp_latest.json()["id"] == intel_data["id"]

    # Clean only our specific db override
    app.dependency_overrides.pop(get_db, None)
