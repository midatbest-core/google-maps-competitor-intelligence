import pytest
from sqlalchemy.orm import Session
from app.models.post import Post
from app.models.analysis import AIAnalysis, PostEmbedding
from app.models.project import Project
from app.models.competitor import ProjectCompetitor
from app.models.profile import BusinessProfile
from app.services.analysis_service import AnalysisService
from app.services.analytics_service import AnalyticsService
from app.services.similarity_service import SimilarityService
from app.providers.ai.fake import FakeAIProvider
from app.providers.embedding.fake import FakeEmbeddingProvider
from app.schemas.analysis import AIAnalysisResult
from app.prompts.analysis_v1 import ANALYSIS_PROMPT_VERSION

@pytest.fixture
def fake_ai():
    return FakeAIProvider()

@pytest.fixture
def fake_embed():
    return FakeEmbeddingProvider()

@pytest.fixture
def analysis_service(db, fake_ai, fake_embed):
    return AnalysisService(db, fake_ai, fake_embed)

@pytest.fixture
def analytics_service(db):
    return AnalyticsService(db)

@pytest.fixture
def similarity_service(db):
    return SimilarityService(db)

@pytest.mark.asyncio
async def test_valid_ai_response_and_idempotency(db: Session, analysis_service):
    biz = BusinessProfile(business_name="Test Biz")
    db.add(biz)
    db.commit()
    
    post = Post(business_id=biz.id, fingerprint="fp-test", text_content="Test content")
    db.add(post)
    db.commit()
    
    analysis1 = await analysis_service.analyze_post(post.id)
    assert analysis1 is not None
    assert analysis1.topic == "Test Topic"
    assert analysis1.provider == "fake_provider"
    
    # Check idempotency
    analysis2 = await analysis_service.analyze_post(post.id)
    assert analysis2.id == analysis1.id
    
    # Check DB count
    count = db.query(AIAnalysis).filter_by(post_id=post.id).count()
    assert count == 1

@pytest.mark.asyncio
async def test_ai_provider_failure(db: Session, fake_embed):
    failing_ai = FakeAIProvider(should_fail=True)
    svc = AnalysisService(db, failing_ai, fake_embed)
    
    biz = BusinessProfile(business_name="Test Biz")
    db.add(biz)
    db.commit()
    post = Post(business_id=biz.id, fingerprint="fp-fail", text_content="Fail content")
    db.add(post)
    db.commit()
    
    res = await svc.analyze_post(post.id)
    assert res is None
    
    # Post remains intact
    assert db.query(Post).filter_by(id=post.id).first() is not None

@pytest.mark.asyncio
async def test_embedding_generation_and_idempotency(db: Session, analysis_service):
    biz = BusinessProfile(business_name="Test Biz")
    db.add(biz)
    db.commit()
    post = Post(business_id=biz.id, fingerprint="fp-embed", text_content="Embed content")
    db.add(post)
    db.commit()
    
    embed1 = await analysis_service.embed_post(post.id)
    assert embed1 is not None
    assert embed1.embedding_model == "fake_embedding_model"
    # dimension check not strict here for pgvector mock but it works
    
    embed2 = await analysis_service.embed_post(post.id)
    assert embed2.id == embed1.id
    
    count = db.query(PostEmbedding).filter_by(post_id=post.id).count()
    assert count == 1

def test_similarity_calculation(similarity_service):
    v1 = [1.0, 0.0, 0.0]
    v2 = [1.0, 0.0, 0.0]
    v3 = [0.0, 1.0, 0.0]
    
    assert similarity_service.calculate_similarity(v1, v2) == 1.0
    assert similarity_service.calculate_similarity(v1, v3) == 0.0

@pytest.mark.asyncio
async def test_analytics_methods(db: Session, analysis_service, analytics_service):
    b1 = BusinessProfile(business_name="B1")
    b2 = BusinessProfile(business_name="B2")
    db.add_all([b1, b2])
    db.commit()
    
    p = Project(name="Proj", own_business_id=b1.id)
    db.add(p)
    db.commit()
    
    pc = ProjectCompetitor(project_id=p.id, business_id=b2.id)
    db.add(pc)
    db.commit()
    
    # Create posts
    post1 = Post(business_id=b1.id, fingerprint="p1", text_content="hello")
    post2 = Post(business_id=b2.id, fingerprint="p2", text_content="world")
    db.add_all([post1, post2])
    db.commit()
    
    await analysis_service.analyze_post(post1.id)
    
    # Custom mock for second post to get different topics
    custom_ai = FakeAIProvider(mock_response=AIAnalysisResult(
        topic="Other Topic", subtopic="Sub", keywords=["other"], content_type="other"
    ))
    svc2 = AnalysisService(db, custom_ai, FakeEmbeddingProvider())
    await svc2.analyze_post(post2.id)
    
    topics = analytics_service.get_topic_frequency(p.id)
    assert len(topics) == 2
    
    coverage = analytics_service.get_competitor_coverage(p.id)
    assert len(coverage) == 2
    
    pct = analytics_service.get_topic_percentage(p.id)
    assert pct[0]["percentage"] == 50.0
    
    kws = analytics_service.get_keyword_frequency(p.id)
    assert len(kws) > 0
    
    patterns = analytics_service.get_publishing_patterns(p.id)
    assert len(patterns["posts_per_competitor"]) == 2
    
    gaps = analytics_service.get_content_gaps(p.id)
    assert "Other Topic" in gaps["topic_gaps"]
    assert "Test Topic" not in gaps["topic_gaps"]
