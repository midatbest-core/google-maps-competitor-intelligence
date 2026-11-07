import json

import httpx
import pytest

from app.models.profile import BusinessProfile
from app.models.project import Project
from app.providers.ai.fake import FakeAIProvider
from app.providers.places import (
    GooglePlacesAPIError,
    GooglePlacesClient,
    GooglePlacesConfigurationError,
    PlacesReviewResult,
)
from app.services.review_service import ReviewService


@pytest.mark.asyncio
async def test_fetch_reviews_uses_stored_place_id_and_correct_field_mask():
    requests = []

    def handler(request: httpx.Request):
        requests.append(request)
        return httpx.Response(
            200,
            json={
                "id": "ChIJStoredPlace123",
                "displayName": {"text": "Example Cafe"},
                "formattedAddress": "1 Main Street",
                "rating": 4.6,
                "userRatingCount": 42,
                "reviews": [
                    {
                        "rating": 5,
                        "text": {"text": "Excellent coffee"},
                        "publishTime": "2026-10-01T10:00:00Z",
                        "relativePublishTimeDescription": "a month ago",
                        "authorAttribution": {"displayName": "Customer"},
                    }
                ],
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        client = GooglePlacesClient("test-api-key", http_client=http_client)
        result = await client.fetch_reviews(
            business_name="Example Cafe",
            address="1 Main Street",
            canonical_source_id="ChIJStoredPlace123",
        )

    assert len(requests) == 1
    request = requests[0]
    assert request.method == "GET"
    assert request.url.path == "/v1/places/ChIJStoredPlace123"
    assert request.headers["X-Goog-Api-Key"] == "test-api-key"
    assert request.headers["X-Goog-FieldMask"] == (
        "id,displayName,formattedAddress,rating,userRatingCount,reviews"
    )
    assert result.place_id == "ChIJStoredPlace123"
    assert result.average_rating == 4.6
    assert result.user_rating_count == 42
    assert result.reviews == [
        {
            "text": "Excellent coffee",
            "rating": 5,
            "publish_time": "2026-10-01T10:00:00Z",
            "relative_publish_time": "a month ago",
            "author_name": "Customer",
        }
    ]


@pytest.mark.asyncio
async def test_text_search_paginates_to_resolve_place_id():
    search_payloads = []
    requested_paths = []

    def handler(request: httpx.Request):
        requested_paths.append(request.url.path)
        if request.url.path.endswith("places:searchText"):
            payload = json.loads(request.content)
            search_payloads.append(payload)
            assert request.headers["X-Goog-FieldMask"] == (
                "places.id,places.displayName,places.formattedAddress,nextPageToken"
            )
            if "pageToken" not in payload:
                return httpx.Response(
                    200,
                    json={
                        "places": [
                            {
                                "id": "ChIJWrongPlace123",
                                "displayName": {"text": "Different Business"},
                                "formattedAddress": "Elsewhere",
                            }
                        ],
                        "nextPageToken": "next-page-token",
                    },
                )
            return httpx.Response(
                200,
                json={
                    "places": [
                        {
                            "id": "ChIJResolvedPlace123",
                            "displayName": {"text": "Example Cafe"},
                            "formattedAddress": "1 Main Street",
                        }
                    ]
                },
            )

        return httpx.Response(
            200,
            json={
                "id": "ChIJResolvedPlace123",
                "displayName": {"text": "Example Cafe"},
                "rating": 4.2,
                "userRatingCount": 10,
                "reviews": [{"rating": 4, "text": {"text": "Good"}}],
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        client = GooglePlacesClient(
            "test-api-key",
            max_search_pages=3,
            http_client=http_client,
        )
        result = await client.fetch_reviews(
            business_name="Example Cafe",
            address="1 Main Street",
        )

    assert search_payloads == [
        {"textQuery": "Example Cafe 1 Main Street", "pageSize": 20},
        {
            "textQuery": "Example Cafe 1 Main Street",
            "pageSize": 20,
            "pageToken": "next-page-token",
        },
    ]
    assert requested_paths == [
        "/v1/places:searchText",
        "/v1/places:searchText",
        "/v1/places/ChIJResolvedPlace123",
    ]
    assert result.place_id == "ChIJResolvedPlace123"
    assert result.reviews[0]["text"] == "Good"


@pytest.mark.asyncio
async def test_stale_stored_place_id_falls_back_to_text_search():
    requested_paths = []

    def handler(request: httpx.Request):
        requested_paths.append(request.url.path)
        if request.url.path == "/v1/places/ChIJStalePlace123":
            return httpx.Response(404, json={"error": {"status": "NOT_FOUND"}})
        if request.url.path.endswith("places:searchText"):
            return httpx.Response(
                200,
                json={
                    "places": [
                        {
                            "id": "ChIJFreshPlace123",
                            "displayName": {"text": "Example Cafe"},
                        }
                    ]
                },
            )
        return httpx.Response(
            200,
            json={
                "id": "ChIJFreshPlace123",
                "reviews": [{"rating": 5, "text": {"text": "Fresh result"}}],
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        client = GooglePlacesClient("test-api-key", http_client=http_client)
        result = await client.fetch_reviews(
            business_name="Example Cafe",
            canonical_source_id="ChIJStalePlace123",
        )

    assert requested_paths == [
        "/v1/places/ChIJStalePlace123",
        "/v1/places:searchText",
        "/v1/places/ChIJFreshPlace123",
    ]
    assert result.place_id == "ChIJFreshPlace123"


@pytest.mark.asyncio
async def test_maps_url_query_place_id_avoids_text_search():
    requested_paths = []

    def handler(request: httpx.Request):
        requested_paths.append(request.url.path)
        return httpx.Response(
            200,
            json={
                "id": "ChIJFromMapsUrl123",
                "reviews": [{"rating": 5, "text": {"text": "Resolved from URL"}}],
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        client = GooglePlacesClient("test-api-key", http_client=http_client)
        result = await client.fetch_reviews(
            business_name="Example Cafe",
            google_maps_url=(
                "https://www.google.com/maps/search/?api=1"
                "&query=Example+Cafe&query_place_id=ChIJFromMapsUrl123"
            ),
        )

    assert requested_paths == ["/v1/places/ChIJFromMapsUrl123"]
    assert result.place_id == "ChIJFromMapsUrl123"


@pytest.mark.asyncio
async def test_missing_api_key_fails_without_an_http_request():
    called = False

    def handler(request: httpx.Request):
        nonlocal called
        called = True
        return httpx.Response(500)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        client = GooglePlacesClient(None, http_client=http_client)
        with pytest.raises(GooglePlacesConfigurationError, match="GOOGLE_PLACES_API_KEY"):
            await client.fetch_reviews(business_name="Example Cafe")

    assert called is False


@pytest.mark.asyncio
async def test_places_quota_error_is_safe_and_does_not_expose_key():
    def handler(request: httpx.Request):
        return httpx.Response(429, json={"error": {"message": "quota"}})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        client = GooglePlacesClient("secret-test-key", http_client=http_client)
        with pytest.raises(GooglePlacesAPIError) as exc_info:
            await client.fetch_reviews(business_name="Example Cafe")

    assert "quota" in str(exc_info.value).lower()
    assert "secret-test-key" not in str(exc_info.value)


@pytest.mark.asyncio
async def test_review_service_persists_resolved_place_id_and_real_review_count(db):
    class StubPlacesClient:
        async def fetch_reviews(self, **kwargs):
            assert kwargs["business_name"] == "Example Cafe"
            return PlacesReviewResult(
                place_id="ChIJPersistedPlace123",
                display_name="Example Cafe",
                formatted_address="1 Main Street",
                average_rating=4.7,
                user_rating_count=200,
                reviews=[
                    {"text": "Excellent", "rating": 5},
                    {"text": "Slow delivery", "rating": 3},
                ],
            )

    business = BusinessProfile(
        business_name="Example Cafe",
        google_maps_url="https://maps.google.com/?q=Example+Cafe",
        address="1 Main Street",
    )
    project = Project(name="Review Project", own_business=business)
    db.add(project)
    db.commit()

    service = ReviewService(
        db,
        FakeAIProvider(),
        places_client=StubPlacesClient(),
    )
    intelligence = await service.analyze_project_reviews(project.id)

    db.refresh(business)
    assert business.canonical_source_id == "ChIJPersistedPlace123"
    assert intelligence.reviews_analyzed_count == 2
    assert intelligence.average_rating == 4.7
    assert intelligence.analysis_provider == "fake_provider"
