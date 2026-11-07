from __future__ import annotations

from dataclasses import dataclass
import logging
import re
from typing import Any
from urllib.parse import parse_qs, quote, urlparse

import httpx


logger = logging.getLogger(__name__)

PLACES_API_BASE_URL = "https://places.googleapis.com/v1"
TEXT_SEARCH_FIELD_MASK = "places.id,places.displayName,places.formattedAddress,nextPageToken"
PLACE_DETAILS_FIELD_MASK = (
    "id,displayName,formattedAddress,rating,userRatingCount,reviews"
)
PLACE_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,255}$")


class GooglePlacesConfigurationError(ValueError):
    """Raised when Places API configuration is missing or rejected."""


class GooglePlacesResolutionError(ValueError):
    """Raised when a business cannot be mapped confidently to a Place ID."""


class GooglePlacesAPIError(RuntimeError):
    """Raised when Google Places is temporarily unavailable or rate limited."""


class _PlaceNotFoundError(GooglePlacesResolutionError):
    pass


@dataclass(frozen=True)
class PlacesReviewResult:
    place_id: str
    display_name: str | None
    formatted_address: str | None
    average_rating: float | None
    user_rating_count: int | None
    reviews: list[dict[str, Any]]


class GooglePlacesClient:
    def __init__(
        self,
        api_key: str | None,
        *,
        timeout_seconds: float = 20.0,
        max_search_pages: int = 3,
        http_client: httpx.AsyncClient | None = None,
    ):
        self.api_key = (api_key or "").strip()
        self.timeout_seconds = timeout_seconds
        self.max_search_pages = max(1, max_search_pages)
        self.http_client = http_client

    async def fetch_reviews(
        self,
        *,
        business_name: str,
        address: str | None = None,
        canonical_source_id: str | None = None,
        google_maps_url: str | None = None,
    ) -> PlacesReviewResult:
        self._require_api_key()
        client = self.http_client or httpx.AsyncClient(timeout=self.timeout_seconds)
        owns_client = self.http_client is None

        try:
            place_id = self._place_id_from_known_values(
                canonical_source_id,
                google_maps_url,
            )
            if place_id:
                try:
                    return await self._fetch_place_details(client, place_id)
                except _PlaceNotFoundError:
                    logger.info("Stored Place ID is stale; resolving it again")

            place_id = await self._resolve_place_id(
                client,
                business_name=business_name,
                address=address,
            )
            return await self._fetch_place_details(client, place_id)
        finally:
            if owns_client:
                await client.aclose()

    def _require_api_key(self) -> None:
        if not self.api_key:
            raise GooglePlacesConfigurationError(
                "Review provider not configured (missing GOOGLE_PLACES_API_KEY)"
            )

    @staticmethod
    def _place_id_from_known_values(
        canonical_source_id: str | None,
        google_maps_url: str | None,
    ) -> str | None:
        if canonical_source_id and PLACE_ID_PATTERN.fullmatch(canonical_source_id):
            return canonical_source_id

        if not google_maps_url:
            return None

        try:
            query = parse_qs(urlparse(google_maps_url).query)
        except ValueError:
            return None

        for key in ("query_place_id", "place_id"):
            value = query.get(key, [None])[0]
            if value and PLACE_ID_PATTERN.fullmatch(value):
                return value
        return None

    async def _resolve_place_id(
        self,
        client: httpx.AsyncClient,
        *,
        business_name: str,
        address: str | None,
    ) -> str:
        query = " ".join(part.strip() for part in (business_name, address) if part and part.strip())
        if not query:
            raise GooglePlacesResolutionError(
                "Business name or address is required to resolve a Google Place ID"
            )

        candidates: list[dict[str, Any]] = []
        page_token: str | None = None

        for _ in range(self.max_search_pages):
            payload: dict[str, Any] = {"textQuery": query, "pageSize": 20}
            if page_token:
                payload["pageToken"] = page_token

            response = await self._request(
                client,
                "POST",
                f"{PLACES_API_BASE_URL}/places:searchText",
                field_mask=TEXT_SEARCH_FIELD_MASK,
                json=payload,
                operation="Place ID resolution",
            )
            page_candidates = response.get("places") or []
            candidates.extend(candidate for candidate in page_candidates if candidate.get("id"))

            exact_match = self._best_candidate(
                page_candidates,
                business_name=business_name,
                address=address,
                require_confident_match=True,
            )
            if exact_match:
                return exact_match["id"]

            page_token = response.get("nextPageToken")
            if not page_token:
                break

        candidate = self._best_candidate(
            candidates,
            business_name=business_name,
            address=address,
            require_confident_match=False,
        )
        if not candidate:
            raise GooglePlacesResolutionError(
                f"Could not resolve a Google Place ID for business '{business_name}'"
            )
        return candidate["id"]

    @classmethod
    def _best_candidate(
        cls,
        candidates: list[dict[str, Any]],
        *,
        business_name: str,
        address: str | None,
        require_confident_match: bool,
    ) -> dict[str, Any] | None:
        scored = [
            (cls._candidate_score(candidate, business_name, address), candidate)
            for candidate in candidates
            if candidate.get("id")
        ]
        if not scored:
            return None

        scored.sort(key=lambda item: item[0], reverse=True)
        score, candidate = scored[0]
        if score >= 100:
            return candidate
        if not require_confident_match and (score >= 60 or len(scored) == 1):
            return candidate
        return None

    @classmethod
    def _candidate_score(
        cls,
        candidate: dict[str, Any],
        business_name: str,
        address: str | None,
    ) -> int:
        expected_name = cls._normalize_text(business_name)
        candidate_name = cls._normalize_text(
            (candidate.get("displayName") or {}).get("text", "")
        )
        score = 0
        if candidate_name == expected_name and expected_name:
            score = 100
        elif expected_name and candidate_name and (
            expected_name in candidate_name or candidate_name in expected_name
        ):
            score = 70

        expected_address = cls._normalize_text(address or "")
        candidate_address = cls._normalize_text(candidate.get("formattedAddress") or "")
        if expected_address and candidate_address and (
            expected_address in candidate_address or candidate_address in expected_address
        ):
            score += 20
        return score

    @staticmethod
    def _normalize_text(value: str) -> str:
        return " ".join(re.findall(r"[a-z0-9]+", value.casefold()))

    async def _fetch_place_details(
        self,
        client: httpx.AsyncClient,
        place_id: str,
    ) -> PlacesReviewResult:
        data = await self._request(
            client,
            "GET",
            f"{PLACES_API_BASE_URL}/places/{quote(place_id, safe='')}",
            field_mask=PLACE_DETAILS_FIELD_MASK,
            operation="review retrieval",
            not_found_is_resolution_error=True,
        )

        reviews = []
        for review in data.get("reviews") or []:
            text_value = (review.get("text") or {}).get("text")
            if not text_value:
                text_value = (review.get("originalText") or {}).get("text")
            if not text_value:
                continue
            reviews.append(
                {
                    "text": text_value,
                    "rating": review.get("rating"),
                    "publish_time": review.get("publishTime"),
                    "relative_publish_time": review.get(
                        "relativePublishTimeDescription"
                    ),
                    "author_name": (review.get("authorAttribution") or {}).get(
                        "displayName"
                    ),
                }
            )

        return PlacesReviewResult(
            place_id=data.get("id") or place_id,
            display_name=(data.get("displayName") or {}).get("text"),
            formatted_address=data.get("formattedAddress"),
            average_rating=data.get("rating"),
            user_rating_count=data.get("userRatingCount"),
            reviews=reviews,
        )

    async def _request(
        self,
        client: httpx.AsyncClient,
        method: str,
        url: str,
        *,
        field_mask: str,
        operation: str,
        not_found_is_resolution_error: bool = False,
        json: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        headers = {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": self.api_key,
            "X-Goog-FieldMask": field_mask,
        }
        try:
            response = await client.request(method, url, headers=headers, json=json)
        except httpx.TimeoutException as exc:
            raise GooglePlacesAPIError(f"Google Places {operation} timed out") from exc
        except httpx.RequestError as exc:
            raise GooglePlacesAPIError(
                f"Google Places {operation} could not be reached"
            ) from exc

        if response.status_code == 404 and not_found_is_resolution_error:
            raise _PlaceNotFoundError("Google Place ID was not found or is no longer valid")
        if response.status_code in (401, 403):
            raise GooglePlacesConfigurationError(
                "Google Places rejected the API key or the Places API (New) is not enabled"
            )
        if response.status_code == 429:
            raise GooglePlacesAPIError("Google Places request quota was exceeded")
        if response.status_code >= 500:
            raise GooglePlacesAPIError("Google Places is temporarily unavailable")
        if response.status_code >= 400:
            raise GooglePlacesResolutionError(
                f"Google Places rejected the {operation} request"
            )

        try:
            payload = response.json()
        except ValueError as exc:
            raise GooglePlacesAPIError(
                f"Google Places returned an invalid {operation} response"
            ) from exc
        if not isinstance(payload, dict):
            raise GooglePlacesAPIError(
                f"Google Places returned an invalid {operation} response"
            )
        return payload
