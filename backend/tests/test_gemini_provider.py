import json

import httpx
import pytest

from app.core.config import settings
from app.models.profile import BusinessProfile
from app.models.project import Project
from app.providers.ai.factory import get_ai_provider
from app.providers.ai.gemini import (
    GeminiAPIError,
    GeminiConfigurationError,
    GeminiProvider,
    GeminiResponseError,
)
from app.providers.places import PlacesReviewResult
from app.services.review_service import ReviewService


def _gemini_response(data: dict) -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "candidates": [
                {"content": {"parts": [{"text": json.dumps(data)}]}}
            ],
            "usageMetadata": {"promptTokenCount": 10, "candidatesTokenCount": 20},
        },
    )


def _generated_content() -> dict:
    return {
        "topic": "Local coffee",
        "title": "Fresh coffee nearby",
        "body": "Visit us for locally roasted coffee.",
        "keywords": ["local coffee", "fresh roast"],
        "cta": "Visit today",
        "offer": None,
        "image_concept": "A cup of coffee beside freshly roasted beans",
        "content_type": "Update",
        "rationale": "Highlights a popular local product.",
    }


def _review_analysis() -> dict:
    return {
        "overall_sentiment": "positive",
        "sentiment_breakdown": {
            "positive": 80,
            "neutral": 10,
            "negative": 10,
        },
        "praise_themes": ["Friendly staff"],
        "complaint_themes": ["Slow service"],
        "pain_points": ["Waiting time"],
        "customer_needs": ["Faster service"],
        "frequently_mentioned_services": ["Coffee"],
        "strengths": ["Hospitality"],
        "weaknesses": ["Queue management"],
        "business_opportunities": ["Mobile ordering"],
        "recommended_actions": ["Add online ordering"],
    }


@pytest.mark.asyncio
async def test_generate_content_uses_configured_model_and_structured_output():
    captured = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured["request"] = request
        captured["payload"] = json.loads(request.content)
        return _gemini_response(_generated_content())

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler)
    ) as client:
        provider = GeminiProvider(
            "test-secret-key",
            model="gemini-2.5-flash",
            http_client=client,
        )
        raw_text, raw_response = await provider.generate_content(
            "Generate one Google Maps update"
        )

    assert provider.provider_name == "gemini"
    assert provider.model_name == "gemini-2.5-flash"
    assert json.loads(raw_text) == _generated_content()
    assert raw_response["usageMetadata"]["promptTokenCount"] == 10
    request = captured["request"]
    assert request.url.path.endswith(
        "/models/gemini-2.5-flash:generateContent"
    )
    assert request.headers["x-goog-api-key"] == "test-secret-key"
    generation_config = captured["payload"]["generationConfig"]
    assert generation_config["responseMimeType"] == "application/json"
    assert generation_config["responseJsonSchema"]["title"] == "AIStructuredOutput"


@pytest.mark.asyncio
async def test_review_analysis_sends_real_reviews_and_validates_result():
    captured = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured["payload"] = json.loads(request.content)
        return _gemini_response(_review_analysis())

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler)
    ) as client:
        provider = GeminiProvider("test-key", http_client=client)
        result, _ = await provider.analyze_reviews(
            "Analyze these business reviews.",
            "Rating: 5 - Excellent coffee\n---\nRating: 2 - Service was slow",
        )

    prompt = captured["payload"]["contents"][0]["parts"][0]["text"]
    assert "Excellent coffee" in prompt
    assert "Service was slow" in prompt
    assert "untrusted customer data" in prompt
    assert result.sentiment_breakdown.positive == 80
    assert result.recommended_actions == ["Add online ordering"]
    schema = captured["payload"]["generationConfig"]["responseJsonSchema"]
    assert schema["title"] == "AIReviewAnalysisResult"


@pytest.mark.asyncio
async def test_analyze_post_returns_validated_structured_result():
    analysis = {
        "topic": "Coffee",
        "subtopic": "New roast",
        "keywords": ["coffee"],
        "content_type": "product/service",
        "cta_type": "Visit website",
        "offer_or_promotion": "no offer",
        "sentiment": "positive",
        "summary": "A new coffee roast is available.",
        "confidence": 0.94,
    }

    async def handler(request: httpx.Request) -> httpx.Response:
        return _gemini_response(analysis)

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler)
    ) as client:
        provider = GeminiProvider("test-key", http_client=client)
        result, _ = await provider.analyze_post("Analyze this post", "post text")

    assert result.topic == "Coffee"
    assert result.confidence == 0.94


@pytest.mark.asyncio
async def test_missing_api_key_fails_without_making_request():
    called = False

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal called
        called = True
        return _gemini_response(_generated_content())

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler)
    ) as client:
        provider = GeminiProvider(None, http_client=client)
        with pytest.raises(
            GeminiConfigurationError, match="GEMINI_API_KEY is not configured"
        ):
            await provider.generate_content("Generate content")

    assert called is False


@pytest.mark.asyncio
async def test_api_error_does_not_expose_key_or_response_body():
    secret = "super-secret-gemini-key"

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            403,
            json={"error": {"message": f"credential {secret} was rejected"}},
        )

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler)
    ) as client:
        provider = GeminiProvider(secret, http_client=client)
        with pytest.raises(GeminiConfigurationError) as exc_info:
            await provider.generate_content("Generate content")

    assert secret not in str(exc_info.value)
    assert "was rejected" not in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_timeout_is_reported_as_safe_provider_error():
    async def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("socket timed out", request=request)

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler)
    ) as client:
        provider = GeminiProvider("test-key", http_client=client)
        with pytest.raises(GeminiAPIError, match="request timed out"):
            await provider.generate_content("Generate content")


@pytest.mark.asyncio
async def test_malformed_or_schema_invalid_responses_are_rejected():
    responses = [
        httpx.Response(200, json={"candidates": []}),
        _gemini_response({"unexpected": "shape"}),
    ]

    async def handler(request: httpx.Request) -> httpx.Response:
        return responses.pop(0)

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler)
    ) as client:
        provider = GeminiProvider("test-key", http_client=client)
        with pytest.raises(GeminiResponseError, match="no usable response"):
            await provider.generate_content("Generate content")
        with pytest.raises(GeminiResponseError, match="required schema"):
            await provider.generate_content("Generate content")


@pytest.mark.asyncio
async def test_review_percentages_must_total_one_hundred():
    invalid = _review_analysis()
    invalid["sentiment_breakdown"] = {
        "positive": 60,
        "neutral": 10,
        "negative": 10,
    }

    async def handler(request: httpx.Request) -> httpx.Response:
        return _gemini_response(invalid)

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler)
    ) as client:
        provider = GeminiProvider("test-key", http_client=client)
        with pytest.raises(GeminiResponseError, match="required schema"):
            await provider.analyze_reviews("Analyze", "Rating: 5 - Great")


def test_factory_applies_gemini_model_and_timeout(monkeypatch):
    monkeypatch.setattr(settings, "APP_ENV", "development")
    monkeypatch.setattr(settings, "AI_PROVIDER", "gemini")
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "factory-test-key")
    monkeypatch.setattr(settings, "GEMINI_MODEL", "models/gemini-2.5-flash")
    monkeypatch.setattr(settings, "GEMINI_TIMEOUT_SECONDS", 12.5)

    provider = get_ai_provider()

    assert isinstance(provider, GeminiProvider)
    assert provider.model_name == "gemini-2.5-flash"
    assert provider.timeout_seconds == 12.5


@pytest.mark.asyncio
async def test_review_service_analyzes_reviews_fetched_by_places_client(db):
    captured = {}

    class StubPlacesClient:
        async def fetch_reviews(self, **kwargs):
            return PlacesReviewResult(
                place_id="ChIJGeminiReview123",
                display_name="Gemini Cafe",
                formatted_address="2 Main Street",
                average_rating=4.2,
                user_rating_count=50,
                reviews=[
                    {"text": "Excellent coffee", "rating": 5},
                    {"text": "Service was slow", "rating": 3},
                ],
            )

    async def handler(request: httpx.Request) -> httpx.Response:
        captured["payload"] = json.loads(request.content)
        return _gemini_response(_review_analysis())

    business = BusinessProfile(
        business_name="Gemini Cafe",
        address="2 Main Street",
    )
    project = Project(name="Gemini Review Project", own_business=business)
    db.add(project)
    db.commit()

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler)
    ) as client:
        service = ReviewService(
            db,
            GeminiProvider("test-key", http_client=client),
            places_client=StubPlacesClient(),
        )
        intelligence = await service.analyze_project_reviews(project.id)

    prompt = captured["payload"]["contents"][0]["parts"][0]["text"]
    assert "Rating: 5 - Excellent coffee" in prompt
    assert "Rating: 3 - Service was slow" in prompt
    assert intelligence.reviews_analyzed_count == 2
    assert intelligence.overall_sentiment == "positive"
    assert intelligence.positive_percentage == 80
    assert intelligence.analysis_provider == "gemini"
    assert intelligence.model_version == "gemini-3.5-flash-lite"


@pytest.mark.asyncio
async def test_unavailable_model_error_is_safe_and_actionable():
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            404,
            json={
                "error": {
                    "message": "upstream detail containing secret-test-key",
                    "status": "NOT_FOUND",
                }
            },
        )

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler)
    ) as client:
        provider = GeminiProvider(
            "secret-test-key",
            model="retired-model",
            http_client=client,
        )
        with pytest.raises(GeminiConfigurationError) as exc_info:
            await provider.generate_content("Generate content")

    message = str(exc_info.value)
    assert "retired-model" in message
    assert "unavailable" in message
    assert "secret-test-key" not in message
    assert "upstream detail" not in message
