import json

import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session
from app.models.project import Project
from app.models.profile import BusinessProfile
from app.models.analysis import GeneratedContent
from app.models.discovery import DiscoveryRun, DiscoveryCandidate
from app.schemas.generation import GenerationRequest, RegenerateRequest
from app.services.generation_service import GenerationService
from app.providers.ai.fake import FakeAIProvider
from app.providers.embedding.fake import FakeEmbeddingProvider
from app.models.analysis import AIAnalysis
from app.models.post import Post
from app.models.competitor import ProjectCompetitor
from app.models.review import ReviewIntelligence
from app.api import generation as generation_api

@pytest.fixture
def fake_ai_provider():
    return FakeAIProvider()

@pytest.fixture
def fake_embedding_provider():
    return FakeEmbeddingProvider()

@pytest.fixture
def generation_service(db: Session, fake_ai_provider, fake_embedding_provider):
    return GenerationService(db, fake_ai_provider, fake_embedding_provider)

def test_request_generation(db: Session, generation_service):
    p = Project(name="Gen Project")
    db.add(p)
    db.commit()

    # Request 3 ideas
    payload = GenerationRequest(generation_type="IDEA", count=3, topic="Weekend Promo")
    contents = generation_service.request_generation(p.id, payload)
    
    assert len(contents) == 3
    for c in contents:
        assert c.status == "QUEUED"
        assert c.generation_type == "IDEA"
        assert c.topic == "Weekend Promo"
        assert c.project_id == p.id

@pytest.mark.asyncio
async def test_generation_job_idea(db: Session, generation_service):
    p = Project(name="Gen Project")
    db.add(p)
    db.commit()

    payload = GenerationRequest(generation_type="IDEA", count=1)
    contents = generation_service.request_generation(p.id, payload)
    gc = contents[0]

    await generation_service.execute_generation(gc.id)

    db.refresh(gc)
    assert gc.status == "SUCCESS"
    assert gc.generated_idea == "Fake body"
    assert gc.topic == "Fake Topic"
    assert gc.fingerprint is not None
    assert gc.provider == "fake_provider"
    assert gc.prompt_version == "v2-review-aware"

@pytest.mark.asyncio
async def test_generation_job_full_copy(db: Session, generation_service):
    p = Project(name="Gen Project")
    db.add(p)
    db.commit()

    payload = GenerationRequest(generation_type="FULL", count=1)
    contents = generation_service.request_generation(p.id, payload)
    gc = contents[0]

    await generation_service.execute_generation(gc.id)

    db.refresh(gc)
    assert gc.status == "SUCCESS"
    assert gc.full_copy == "Fake body"
    assert gc.generated_idea is None

@pytest.mark.asyncio
async def test_duplicate_rejection(db: Session, generation_service):
    p = Project(name="Gen Project")
    db.add(p)
    db.commit()

    # First generation
    payload = GenerationRequest(generation_type="FULL", count=1)
    contents = generation_service.request_generation(p.id, payload)
    gc1 = contents[0]
    await generation_service.execute_generation(gc1.id)
    
    db.refresh(gc1)
    assert gc1.status == "SUCCESS"

    # Second generation (Fake provider returns same output)
    contents2 = generation_service.request_generation(p.id, payload)
    gc2 = contents2[0]
    await generation_service.execute_generation(gc2.id)

    db.refresh(gc2)
    assert gc2.status == "REJECTED_DUPLICATE"
    assert "Exact text duplicate" in gc2.error_message

@pytest.mark.asyncio
async def test_regeneration(db: Session, generation_service):
    p = Project(name="Gen Project")
    db.add(p)
    db.commit()

    payload = GenerationRequest(generation_type="IDEA", count=1)
    contents = generation_service.request_generation(p.id, payload)
    gc1 = contents[0]
    await generation_service.execute_generation(gc1.id)

    regen_payload = RegenerateRequest(regeneration_reason="Make it funnier")
    gc2 = generation_service.request_regeneration(p.id, gc1.id, regen_payload)

    assert gc2.status == "QUEUED"
    assert gc2.parent_generation_id == gc1.id
    assert gc2.regeneration_reason == "Make it funnier"
    assert gc2.id != gc1.id

@pytest.mark.asyncio
async def test_provider_failure(db: Session):
    fake_provider = FakeAIProvider(should_fail=True)
    svc = GenerationService(db, fake_provider)

    p = Project(name="Gen Project")
    db.add(p)
    db.commit()

    payload = GenerationRequest(generation_type="IDEA", count=1)
    contents = svc.request_generation(p.id, payload)
    gc = contents[0]

    await svc.execute_generation(gc.id)

    db.refresh(gc)
    assert gc.status == "FAILED"
    assert "Fake provider failure" in gc.error_message

def test_project_isolation(db: Session, generation_service):
    pA = Project(name="A")
    pB = Project(name="B")
    db.add_all([pA, pB])
    db.commit()

    payload = GenerationRequest(generation_type="IDEA", count=1)
    contents = generation_service.request_generation(pA.id, payload)
    gc = contents[0]

    # Project B tries to get it
    with pytest.raises(ValueError, match="Content not found"):
        generation_service.get_generated_content(pB.id, gc.id)

    # Project B tries to regenerate it
    with pytest.raises(ValueError, match="Content not found"):
        generation_service.request_regeneration(pB.id, gc.id, RegenerateRequest())

@pytest.mark.asyncio
async def test_semantic_duplicate(db: Session, generation_service):
    p = Project(name="Gen Project Sem")
    db.add(p)
    db.commit()

    # First generation
    payload = GenerationRequest(generation_type="FULL", count=1)
    gc1 = generation_service.request_generation(p.id, payload)[0]
    await generation_service.execute_generation(gc1.id)
    db.refresh(gc1)
    assert gc1.status == "SUCCESS"

    # Second generation (same output text -> EXACT DUPLICATE)
    gc2 = generation_service.request_generation(p.id, payload)[0]
    await generation_service.execute_generation(gc2.id)
    db.refresh(gc2)
    assert gc2.status == "REJECTED_DUPLICATE"
    assert "Exact text duplicate" in gc2.error_message

    # Bypass exact duplicate by mocking AI Provider to return something semantically similar
    # In fake embedding, hash of first 4 chars of MD5 determines angle.
    # We will just insert a GeneratedContent with exact same embedding but different text.
    gc3 = GeneratedContent(
        project_id=p.id,
        generation_type="FULL",
        status="QUEUED"
    )
    db.add(gc3)
    db.commit()
    
    # We'll mock ai_provider for this run
    generation_service.ai_provider = FakeAIProvider()
    original_generate = generation_service.ai_provider.generate_content
    
    async def mock_generate(*args, **kwargs):
        # Return different text but we'll manually ensure it has the same embedding by returning
        # a text that has the same md5 hash prefix, or simply mock embedding provider too.
        return '{"body": "Different text but similar enough", "topic": "topic", "title": "title", "keywords": [], "cta": "cta", "offer": "offer", "image_concept": "img", "content_type": "type", "rationale": "rat"}', {}
    
    generation_service.ai_provider.generate_content = mock_generate
    
    original_embed = generation_service.embedding_provider.generate_embedding
    async def mock_embed(*args, **kwargs):
        return gc1.embedding # Return exact same embedding as gc1
        
    generation_service.embedding_provider.generate_embedding = mock_embed

    await generation_service.execute_generation(gc3.id)
    db.refresh(gc3)
    assert gc3.status == "REJECTED_DUPLICATE"
    assert "Semantic duplicate found" in gc3.error_message

@pytest.mark.asyncio
async def test_content_gaps_logic(db: Session, generation_service):
    p = Project(name="Gap Project")
    b_own = BusinessProfile(business_name="Own Business")
    b_comp = BusinessProfile(business_name="Comp Business")
    db.add_all([p, b_own, b_comp])
    db.commit()
    
    p.own_business_id = b_own.id
    pc = ProjectCompetitor(project_id=p.id, business_id=b_comp.id)
    db.add(pc)
    db.commit()
    
    # Competitor posts with topics
    post_c = Post(business_id=b_comp.id, text_content="Competitor post", source_url="http://c", fingerprint="fp_c")
    post_o = Post(business_id=b_own.id, text_content="Own post", source_url="http://o", fingerprint="fp_o")
    db.add_all([post_c, post_o])
    db.commit()
    
    ai_c = AIAnalysis(post_id=post_c.id, topic="Weekend Offer", keywords=["promo", "weekend"], content_type="offer", provider="fake", model_name="fake")
    ai_o = AIAnalysis(post_id=post_o.id, topic="Informational", keywords=["info"], content_type="info", provider="fake", model_name="fake")
    db.add_all([ai_c, ai_o])
    db.commit()
    
    # Check what intel context builds
    context = generation_service._build_intel_context(p.id)
    assert "Topic Gaps" in context
    assert "Weekend Offer" in context
    assert "Keyword Gaps" in context
    assert "promo" in context
    assert "Content Type Gaps" in context
    assert "offer" in context

@pytest.mark.asyncio
async def test_malformed_ai_output(db: Session, generation_service):
    p = Project(name="Malformed Project")
    db.add(p)
    db.commit()

    gc = GeneratedContent(project_id=p.id, generation_type="FULL", status="QUEUED")
    db.add(gc)
    db.commit()
    
    async def mock_generate(*args, **kwargs):
        # Missing 'body' which is required (or some other malformed data)
        # Actually our schema doesn't strictly require body? Let's check AIStructuredOutput
        # Wait, if it's invalid JSON completely
        return 'Not JSON at all', {}
    
    generation_service.ai_provider.generate_content = mock_generate
    await generation_service.execute_generation(gc.id)
    db.refresh(gc)
    assert gc.status == "FAILED"
    assert "invalid JSON" in gc.error_message


@pytest.mark.asyncio
async def test_generation_uses_reviews_for_selected_business_only(db: Session):
    class ReviewAwareProvider(FakeAIProvider):
        def __init__(self):
            super().__init__()
            self.prompt = None

        async def generate_content(self, prompt: str):
            self.prompt = prompt
            response = {
                "topic": "Easier pickup planning",
                "title": "Plan your next pickup",
                "body": (
                    "Looking for a smoother visit? Contact us to confirm the best "
                    "pickup time for your order."
                ),
                "keywords": ["pickup", "local service"],
                "cta": "Contact us",
                "offer": None,
                "image_concept": "A prepared order at a pickup counter",
                "content_type": "Update",
                "rationale": "Addresses customer feedback about waiting times.",
            }
            return json.dumps(response), {"raw": response}

    selected_business = BusinessProfile(business_name="Selected Cafe")
    unrelated_business = BusinessProfile(business_name="Unrelated Cafe")
    project = Project(name="Review-Aware Project", own_business=selected_business)
    db.add_all([project, unrelated_business])
    db.commit()

    selected_reviews = ReviewIntelligence(
        project_id=project.id,
        business_id=selected_business.id,
        reviews_analyzed_count=5,
        overall_sentiment="mixed",
        praise_themes=["Friendly staff"],
        complaint_themes=["Long pickup waits"],
        pain_points=["Unclear pickup timing"],
        customer_needs=["Predictable pickup times"],
        business_opportunities=["Clarify pickup planning"],
    )
    unrelated_reviews = ReviewIntelligence(
        project_id=project.id,
        business_id=unrelated_business.id,
        reviews_analyzed_count=5,
        praise_themes=["Rooftop seating"],
        complaint_themes=["Limited parking"],
        pain_points=["Parking availability"],
        business_opportunities=["Valet parking"],
    )
    db.add_all([selected_reviews, unrelated_reviews])
    db.commit()

    provider = ReviewAwareProvider()
    service = GenerationService(db, provider)
    generated = service.request_generation(
        project.id,
        GenerationRequest(generation_type="FULL"),
    )[0]

    await service.execute_generation(generated.id)

    db.refresh(generated)
    assert generated.status == "SUCCESS"
    assert "confirm the best pickup time" in generated.full_copy
    assert "Business: Selected Cafe" in provider.prompt
    assert "Customer praise themes: Friendly staff" in provider.prompt
    assert "Customer complaint themes: Long pickup waits" in provider.prompt
    assert "Customer pain points: Unclear pickup timing" in provider.prompt
    assert "Business opportunities: Clarify pickup planning" in provider.prompt
    assert "Rooftop seating" not in provider.prompt
    assert "Limited parking" not in provider.prompt
    assert "Never invent customer opinions" in provider.prompt


@pytest.mark.asyncio
async def test_generation_succeeds_without_review_intelligence(db: Session):
    class CapturingProvider(FakeAIProvider):
        def __init__(self):
            super().__init__()
            self.prompt = None

        async def generate_content(self, prompt: str):
            self.prompt = prompt
            return await super().generate_content(prompt)

    business = BusinessProfile(business_name="No Reviews Cafe")
    project = Project(name="No Reviews Project", own_business=business)
    db.add(project)
    db.commit()

    provider = CapturingProvider()
    service = GenerationService(db, provider)
    generated = service.request_generation(
        project.id,
        GenerationRequest(generation_type="FULL"),
    )[0]

    await service.execute_generation(generated.id)

    db.refresh(generated)
    assert generated.status == "SUCCESS"
    assert generated.full_copy == "Fake body"
    assert "CUSTOMER REVIEW EVIDENCE FOR SELECTED BUSINESS" not in provider.prompt
    assert "When review evidence is absent" in provider.prompt


@pytest.mark.asyncio
async def test_enqueue_failure_marks_unsubmitted_content_failed(db, monkeypatch):
    async def unavailable_pool():
        raise ConnectionError("synthetic Redis outage")

    monkeypatch.setattr(generation_api, "get_redis_pool", unavailable_pool)
    project = Project(name="Queue Failure Project")
    db.add(project)
    db.commit()
    service = GenerationService(db, FakeAIProvider())

    with pytest.raises(HTTPException) as exc_info:
        await generation_api.start_generation(
            project.id,
            GenerationRequest(generation_type="IDEA", count=2),
            service,
        )

    assert exc_info.value.status_code == 503
    assert exc_info.value.detail == "Generation queue is unavailable"
    records = db.query(GeneratedContent).filter_by(project_id=project.id).all()
    assert len(records) == 2
    assert {record.status for record in records} == {"FAILED"}
    assert all(
        record.error_message == "Failed to enqueue generation job"
        for record in records
    )

