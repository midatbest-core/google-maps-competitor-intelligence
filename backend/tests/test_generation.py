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


@pytest.mark.asyncio
async def test_marketing_opportunities_workflow_and_context(db: Session, generation_service):
    """
    Verifies that MARKETING_OPPORTUNITIES workflow mode creates a marketing opportunity,
    executes with v3-marketing-intelligence prompt version, and stores evidence in source_context.
    """
    p = Project(name="Marketing Opp Project")
    db.add(p)
    db.commit()

    payload = GenerationRequest(
        generation_type="IDEA",
        workflow_mode="MARKETING_OPPORTUNITIES",
        count=1
    )
    contents = generation_service.request_generation(p.id, payload)
    assert len(contents) == 1
    gc = contents[0]
    assert gc.status == "QUEUED"
    assert gc.source_context.get("workflow_mode") == "MARKETING_OPPORTUNITIES"

    await generation_service.execute_generation(gc.id)
    db.refresh(gc)
    assert gc.status == "SUCCESS"
    assert gc.prompt_version == "v3-marketing-intelligence"
    assert gc.generated_idea is not None
    assert "rationale" in gc.source_context
    assert "evidence" in gc.source_context


@pytest.mark.asyncio
async def test_create_content_workflow_mode(db: Session, generation_service):
    """
    Verifies that CREATE_CONTENT workflow mode produces a FULL content draft
    using v3-marketing-intelligence prompt version.
    """
    p = Project(name="Create Content Project")
    db.add(p)
    db.commit()

    payload = GenerationRequest(
        generation_type="FULL",
        workflow_mode="CREATE_CONTENT",
        topic="Seasonal Specials",
        content_type="Offer"
    )
    contents = generation_service.request_generation(p.id, payload)
    assert len(contents) == 1
    gc = contents[0]
    assert gc.status == "QUEUED"
    assert gc.generation_type == "FULL"
    assert gc.source_context.get("workflow_mode") == "CREATE_CONTENT"

    await generation_service.execute_generation(gc.id)
    db.refresh(gc)
    assert gc.status == "SUCCESS"
    assert gc.prompt_version == "v3-marketing-intelligence"
    assert gc.full_copy is not None


@pytest.mark.asyncio
async def test_generation_timeout_transitions_to_failed(db: Session, generation_service):
    """
    Verifies that slow AI generation that exceeds the timeout is caught
    and transitions the database record to FAILED with a timeout message.
    """
    import asyncio

    p = Project(name="Timeout Project")
    db.add(p)
    db.commit()

    gc = GeneratedContent(
        project_id=p.id,
        generation_type="IDEA",
        topic="Slow Topic",
        status="QUEUED"
    )
    db.add(gc)
    db.commit()

    async def hanging_generate(*args, **kwargs):
        await asyncio.sleep(2.0)
        return '{"body": "never returned"}', {}

    generation_service.ai_provider.generate_content = hanging_generate

    # Execute with a 0.1s timeout
    await generation_service.execute_generation(gc.id, timeout_seconds=0.1)

    db.refresh(gc)
    assert gc.status == "FAILED"
    assert "timed out after" in gc.error_message


def test_reconcile_stale_generations(db: Session):
    """
    Verifies that reconciliation distinguishes between:
    - Never dispatched jobs (> 5m) -> FAILED
    - Dispatched jobs legitimately queued -> Preserved as QUEUED (not failed on 10m timer)
    - Stale RUNNING jobs (> 5m execution) -> FAILED
    - Fresh RUNNING jobs (< 5m execution) -> Preserved as RUNNING
    """
    from datetime import datetime, timezone, timedelta

    p = Project(name="Stale Project")
    db.add(p)
    db.commit()

    now = datetime.now(timezone.utc)
    fifteen_mins_ago = now - timedelta(minutes=15)
    six_mins_ago = now - timedelta(minutes=6)
    thirty_secs_ago = now - timedelta(seconds=30)

    # 1. Never dispatched queued job (6 mins old, no dispatched_at) -> Should fail
    never_dispatched = GeneratedContent(
        project_id=p.id,
        generation_type="IDEA",
        status="QUEUED",
        created_at=six_mins_ago,
        source_context={}
    )
    # 2. Legitimately dispatched queued job (15 mins old, dispatched_at set) -> Must stay QUEUED
    legit_queued = GeneratedContent(
        project_id=p.id,
        generation_type="IDEA",
        status="QUEUED",
        created_at=fifteen_mins_ago,
        source_context={"dispatched_at": fifteen_mins_ago.isoformat()}
    )
    # 3. Worker crashed while RUNNING (started 6 mins ago, execution limit 120s) -> Should fail
    crashed_running = GeneratedContent(
        project_id=p.id,
        generation_type="FULL",
        status="RUNNING",
        created_at=fifteen_mins_ago,
        source_context={"started_at": six_mins_ago.isoformat()}
    )
    # 4. Fresh actively running job (started 30s ago) -> Must stay RUNNING
    active_running = GeneratedContent(
        project_id=p.id,
        generation_type="FULL",
        status="RUNNING",
        created_at=fifteen_mins_ago,
        source_context={"started_at": thirty_secs_ago.isoformat()}
    )
    db.add_all([never_dispatched, legit_queued, crashed_running, active_running])
    db.commit()

    reconciled = GenerationService.reconcile_stale_generations(db)
    assert reconciled == 2

    db.refresh(never_dispatched)
    db.refresh(legit_queued)
    db.refresh(crashed_running)
    db.refresh(active_running)

    assert never_dispatched.status == "FAILED"
    assert "never dispatched" in never_dispatched.error_message

    assert legit_queued.status == "QUEUED"
    assert legit_queued.error_message is None

    assert crashed_running.status == "FAILED"
    assert "interrupted or exceeded execution limit" in crashed_running.error_message

    assert active_running.status == "RUNNING"
    assert active_running.error_message is None


def test_list_and_get_proactive_reconciliation(db: Session, generation_service):
    """
    Verifies that get_generated_content and list_generated_content proactively
    reconcile genuine stale items without failing legitimately queued items.
    """
    from datetime import datetime, timezone, timedelta

    p = Project(name="Proactive Project")
    db.add(p)
    db.commit()

    old_time = datetime.now(timezone.utc) - timedelta(hours=2)
    # Never dispatched stale item
    stale_item = GeneratedContent(
        project_id=p.id,
        generation_type="IDEA",
        status="QUEUED",
        created_at=old_time,
        source_context={}
    )
    # Legitimately queued item waiting 12 minutes (max_jobs=1 prior scrape running)
    twelve_mins_ago = datetime.now(timezone.utc) - timedelta(minutes=12)
    legit_item = GeneratedContent(
        project_id=p.id,
        generation_type="IDEA",
        status="QUEUED",
        created_at=twelve_mins_ago,
        source_context={"dispatched_at": twelve_mins_ago.isoformat()}
    )
    db.add_all([stale_item, legit_item])
    db.commit()

    # Proactive get on stale never-dispatched item
    retrieved_stale = generation_service.get_generated_content(p.id, stale_item.id)
    assert retrieved_stale.status == "FAILED"
    assert "never dispatched" in retrieved_stale.error_message

    # Proactive get on legitimately queued item (must NOT fail)
    retrieved_legit = generation_service.get_generated_content(p.id, legit_item.id)
    assert retrieved_legit.status == "QUEUED"


def test_retry_generation_resets_failed_item(db: Session, generation_service):
    """
    Verifies that retry_generation resets a FAILED item to QUEUED,
    clears error_message, preserves item ID, and does not duplicate records.
    """
    p = Project(name="Retry Project")
    db.add(p)
    db.commit()

    gc = GeneratedContent(
        project_id=p.id,
        generation_type="IDEA",
        topic="Retryable Topic",
        status="FAILED",
        error_message="Previous failure"
    )
    db.add(gc)
    db.commit()

    initial_id = gc.id
    retried = generation_service.retry_generation(p.id, gc.id)

    assert retried.id == initial_id
    assert retried.status == "QUEUED"
    assert retried.error_message is None

    # Verify no duplicate was created
    all_items = db.query(GeneratedContent).filter_by(project_id=p.id).all()
    assert len(all_items) == 1


@pytest.mark.asyncio
async def test_worker_generate_content_job_error_handling(db: Session, monkeypatch):
    """
    Verifies that generate_content_job catches unhandled worker exceptions
    and updates the database record to FAILED with error_message.
    """
    from unittest.mock import MagicMock
    from app.workers.main import generate_content_job

    p = Project(name="Worker Error Project")
    db.add(p)
    db.commit()

    gc = GeneratedContent(
        project_id=p.id,
        generation_type="IDEA",
        status="QUEUED"
    )
    db.add(gc)
    db.commit()

    # Monkeypatch execute_generation to raise an unexpected runtime error
    async def mock_fail_execute(*args, **kwargs):
        raise RuntimeError("Simulated worker crash / out-of-memory error")

    monkeypatch.setattr(
        "app.services.generation_service.GenerationService.execute_generation",
        mock_fail_execute
    )
    worker_db = MagicMock(wraps=db)
    worker_db.close = MagicMock()
    worker_db.rollback = MagicMock()
    monkeypatch.setattr("app.workers.main.SessionLocal", lambda: worker_db)

    await generate_content_job(None, gc.id)

    db.refresh(gc)
    assert gc.status == "FAILED"
    assert "Simulated worker crash" in gc.error_message


@pytest.mark.asyncio
async def test_worker_generate_content_job_provider_failure(db: Session, monkeypatch):
    """
    Verifies that if get_ai_provider fails during worker execution,
    the record is still cleanly marked FAILED.
    """
    from app.workers.main import generate_content_job

    class NonClosingSession:
        def __init__(self, s):
            self._s = s
        def close(self):
            pass
        def __getattr__(self, item):
            return getattr(self._s, item)

    p = Project(name="Provider Error Project")
    db.add(p)
    db.commit()

    gc = GeneratedContent(
        project_id=p.id,
        generation_type="IDEA",
        status="QUEUED"
    )
    db.add(gc)
    db.commit()

    def mock_bad_provider():
        raise ValueError("Invalid GEMINI_API_KEY")

    monkeypatch.setattr("app.providers.ai.factory.get_ai_provider", mock_bad_provider)
    monkeypatch.setattr("app.workers.main.SessionLocal", lambda: NonClosingSession(db))

    await generate_content_job(None, gc.id)

    db.refresh(gc)
    assert gc.status == "FAILED"
    assert "Invalid GEMINI_API_KEY" in gc.error_message


@pytest.mark.asyncio
async def test_retry_content_generation_endpoint(db: Session, generation_service, monkeypatch):
    """
    Verifies that POST /projects/{project_id}/content/{content_id}/retry
    resets a failed item to QUEUED, preserves its ID, and enqueues the worker job.
    """
    from app.api.generation import retry_content_generation
    from unittest.mock import AsyncMock

    p = Project(name="API Retry Project")
    db.add(p)
    db.commit()

    gc = GeneratedContent(
        project_id=p.id,
        generation_type="IDEA",
        topic="Retry API Topic",
        status="FAILED",
        error_message="Previous failure"
    )
    db.add(gc)
    db.commit()

    mock_pool = AsyncMock()
    mock_pool.enqueue_job = AsyncMock()
    mock_pool.close = AsyncMock()

    monkeypatch.setattr("app.api.generation.get_redis_pool", AsyncMock(return_value=mock_pool))

    res = await retry_content_generation(
        project_id=p.id,
        content_id=gc.id,
        service=generation_service
    )

    assert res.id == gc.id
    assert res.status == "QUEUED"
    assert res.error_message is None
    assert mock_pool.enqueue_job.await_count == 1


def test_reconciliation_preserves_job_completing_immediately_before(db: Session):
    """
    Verifies that a job that completed successfully immediately before reconciliation
    runs is NOT overwritten or marked FAILED.
    """
    from datetime import datetime, timezone, timedelta

    p = Project(name="Completed Before Reconcile")
    db.add(p)
    db.commit()

    twenty_mins_ago = datetime.now(timezone.utc) - timedelta(minutes=20)
    completed_gc = GeneratedContent(
        project_id=p.id,
        generation_type="IDEA",
        status="SUCCESS",
        generated_idea="Freshly completed content",
        created_at=twenty_mins_ago,
        source_context={"started_at": twenty_mins_ago.isoformat()}
    )
    db.add(completed_gc)
    db.commit()

    reconciled = GenerationService.reconcile_stale_generations(db)
    assert reconciled == 0

    db.refresh(completed_gc)
    assert completed_gc.status == "SUCCESS"
    assert completed_gc.error_message is None


def test_retry_concurrent_requests_atomic_prevention(db: Session, generation_service):
    """
    Verifies that when two simultaneous retry requests arrive for the same record:
    1. The first request atomically claims and transitions to QUEUED.
    2. The second request is rejected (already in progress).
    3. Exactly one transition occurs without duplicates.
    """
    p = Project(name="Concurrent Retry Project")
    db.add(p)
    db.commit()

    gc = GeneratedContent(
        project_id=p.id,
        generation_type="IDEA",
        status="FAILED",
        error_message="Worker error"
    )
    db.add(gc)
    db.commit()

    # Request 1: succeeds
    retried_1 = generation_service.retry_generation(p.id, gc.id)
    assert retried_1.status == "QUEUED"

    # Request 2 (simultaneous): must raise ValueError because row is already QUEUED
    with pytest.raises(ValueError, match="already in progress"):
        generation_service.retry_generation(p.id, gc.id)

    # Verify no duplicates
    all_rows = db.query(GeneratedContent).filter_by(project_id=p.id).all()
    assert len(all_rows) == 1
    assert all_rows[0].status == "QUEUED"


def test_retry_cannot_overwrite_successful_result(db: Session, generation_service):
    """
    Verifies that retry_generation cannot overwrite a successful result.
    """
    p = Project(name="Successful Result Protection")
    db.add(p)
    db.commit()

    gc = GeneratedContent(
        project_id=p.id,
        generation_type="IDEA",
        status="SUCCESS",
        generated_idea="Valuable generated post"
    )
    db.add(gc)
    db.commit()

    with pytest.raises(ValueError, match="already succeeded"):
        generation_service.retry_generation(p.id, gc.id)

    db.refresh(gc)
    assert gc.status == "SUCCESS"
    assert gc.generated_idea == "Valuable generated post"


@pytest.mark.asyncio
async def test_worker_restart_while_job_actively_processing(db: Session):
    """
    Verifies that a worker or API restart does NOT fail a job that is actively
    being processed by another worker (e.g. started 30 seconds ago).
    """
    from datetime import datetime, timezone, timedelta

    p = Project(name="Active Processing Safety")
    db.add(p)
    db.commit()

    now = datetime.now(timezone.utc)
    started_recent = now - timedelta(seconds=25)
    active_gc = GeneratedContent(
        project_id=p.id,
        generation_type="FULL",
        status="RUNNING",
        created_at=now - timedelta(minutes=10),
        source_context={"started_at": started_recent.isoformat(), "heartbeat_at": started_recent.isoformat()}
    )
    db.add(active_gc)
    db.commit()

    # Startup reconciliation executes
    reconciled = GenerationService.reconcile_stale_generations(db)
    assert reconciled == 0

    db.refresh(active_gc)
    assert active_gc.status == "RUNNING"
    assert active_gc.error_message is None


def test_dispatched_job_waiting_45_minutes_remains_queued(db: Session):
    """
    Regression test: Verifies that when max_jobs=1 workers are occupied by multiple
    long-running scrape jobs, a legitimately dispatched generation job waiting 45 minutes
    remains in QUEUED status and is NOT prematurely failed.
    """
    from datetime import datetime, timezone, timedelta

    p = Project(name="Long Queue Wait Project")
    db.add(p)
    db.commit()

    now = datetime.now(timezone.utc)
    forty_five_mins_ago = now - timedelta(minutes=45)

    dispatched_gc = GeneratedContent(
        project_id=p.id,
        generation_type="IDEA",
        status="QUEUED",
        created_at=forty_five_mins_ago,
        source_context={"dispatched_at": forty_five_mins_ago.isoformat()}
    )
    db.add(dispatched_gc)
    db.commit()

    reconciled = GenerationService.reconcile_stale_generations(db)
    assert reconciled == 0

    db.refresh(dispatched_gc)
    assert dispatched_gc.status == "QUEUED"
    assert dispatched_gc.error_message is None

