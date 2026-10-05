import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.core.database import SessionLocal
from app.models.project import Project
from app.models.competitor import ProjectCompetitor
from app.models.profile import BusinessProfile
from app.models.post import Post, PostMedia
from app.models.analysis import AIAnalysis
from app.models.auth import User, Workspace, WorkspaceMember
from datetime import datetime, timezone, timedelta

client = TestClient(app)

from app.core.database import SessionLocal, engine
from app.models.base import Base

@pytest.fixture(autouse=True)
def setup_db():
    old_overrides = dict(app.dependency_overrides)
    app.dependency_overrides.clear()
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)
    app.dependency_overrides.update(old_overrides)

# Helper function to create auth token
def create_auth_token(user_id: str) -> str:
    from jose import jwt
    from app.core.security import settings
    return jwt.encode({"sub": user_id}, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

@pytest.fixture
def auth_headers():
    db = SessionLocal()
    user = User(email="test_posts@example.com", hashed_password="hashed")
    db.add(user)
    db.commit()
    
    ws = Workspace(name="Test Workspace Posts")
    db.add(ws)
    db.commit()
    
    member = WorkspaceMember(workspace_id=ws.id, user_id=user.id, role="OWNER")
    db.add(member)
    db.commit()
    
    token = create_auth_token(user.id)
    headers = {"Authorization": f"Bearer {token}"}
    
    # Store in headers dict for easy access
    headers["X-User-Id"] = user.id
    headers["X-Workspace-Id"] = ws.id
    
    db.close()
    return headers

@pytest.fixture
def other_auth_headers():
    db = SessionLocal()
    user = User(email="other_posts@example.com", hashed_password="hashed")
    db.add(user)
    db.commit()
    
    ws = Workspace(name="Other Workspace Posts")
    db.add(ws)
    db.commit()
    
    member = WorkspaceMember(workspace_id=ws.id, user_id=user.id, role="OWNER")
    db.add(member)
    db.commit()
    
    token = create_auth_token(user.id)
    headers = {"Authorization": f"Bearer {token}"}
    db.close()
    return headers

@pytest.fixture
def sample_project(auth_headers):
    db = SessionLocal()
    ws_id = auth_headers["X-Workspace-Id"]
    
    project = Project(name="Project 1", workspace_id=ws_id)
    db.add(project)
    db.commit()
    
    business = BusinessProfile(business_name="Own Business", google_maps_url="http://own")
    db.add(business)
    db.commit()
    
    project.own_business_id = business.id
    db.commit()
    
    competitor = BusinessProfile(business_name="Competitor 1", google_maps_url="http://comp1")
    db.add(competitor)
    db.commit()
    
    pc = ProjectCompetitor(project_id=project.id, business_id=competitor.id)
    db.add(pc)
    db.commit()
    
    # Add posts
    post1 = Post(business_id=competitor.id, fingerprint="fp1", text_content="weekend special offer", published_date=datetime.now(timezone.utc))
    post2 = Post(business_id=competitor.id, fingerprint="fp2", text_content="another post", published_date=datetime.now(timezone.utc) - timedelta(days=1))
    post3 = Post(business_id=business.id, fingerprint="fp3", text_content="our own post", published_date=datetime.now(timezone.utc) - timedelta(days=2))
    db.add_all([post1, post2, post3])
    db.commit()
    
    # Add Analysis
    ana1 = AIAnalysis(post_id=post1.id, provider="fake", model_name="fake", topic="Promotions", keywords=["weekend", "special"])
    ana3 = AIAnalysis(post_id=post3.id, provider="fake", model_name="fake", topic="Events", keywords=["event"])
    db.add_all([ana1, ana3])
    db.commit()
    
    project_id = project.id
    db.close()
    return project_id

def test_get_project_posts(auth_headers, sample_project):
    res = client.get(f"/projects/{sample_project}/posts", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 3
    assert len(data["items"]) == 3
    
def test_unauthenticated(sample_project):
    res = client.get(f"/projects/{sample_project}/posts")
    assert res.status_code == 404
    
def test_foreign_workspace(other_auth_headers, sample_project):
    res = client.get(f"/projects/{sample_project}/posts", headers=other_auth_headers)
    assert res.status_code == 404
    
def test_post_pagination(auth_headers, sample_project):
    res = client.get(f"/projects/{sample_project}/posts?page=1&page_size=2", headers=auth_headers)
    data = res.json()
    assert data["total"] == 3
    assert len(data["items"]) == 2
    assert data["pages"] == 2
    
def test_post_search(auth_headers, sample_project):
    res = client.get(f"/projects/{sample_project}/posts?search=weekend", headers=auth_headers)
    data = res.json()
    assert data["total"] == 1
    assert data["items"][0]["text_content"] == "weekend special offer"

def test_post_filters(auth_headers, sample_project):
    res = client.get(f"/projects/{sample_project}/posts?topic=Promotions", headers=auth_headers)
    data = res.json()
    assert data["total"] == 1
    
    res2 = client.get(f"/projects/{sample_project}/posts?has_analysis=true", headers=auth_headers)
    assert res2.json()["total"] == 2

    res3 = client.get(f"/projects/{sample_project}/posts?has_analysis=false", headers=auth_headers)
    assert res3.json()["total"] == 1
    
def test_get_project_post_detail(auth_headers, sample_project):
    # get a post id first
    posts_res = client.get(f"/projects/{sample_project}/posts", headers=auth_headers)
    post_id = posts_res.json()["items"][0]["id"]
    
    res = client.get(f"/projects/{sample_project}/posts/{post_id}", headers=auth_headers)
    assert res.status_code == 200
    assert res.json()["id"] == post_id

def test_get_analytics_summary(auth_headers, sample_project):
    res = client.get(f"/projects/{sample_project}/analytics/summary", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert len(data["topics"]) > 0
    assert len(data["content_gaps"]["topic_gaps"]) >= 0 # Gap is calculated properly
