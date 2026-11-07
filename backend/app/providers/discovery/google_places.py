import logging
from typing import List, Optional
import httpx
from app.providers.discovery.base import DiscoveryProvider
from app.schemas.discovery import DiscoveryCandidateSchema
from app.core.config import settings

logger = logging.getLogger(__name__)

PLACES_API_BASE_URL = "https://places.googleapis.com/v1"
DISCOVERY_FIELD_MASK = (
    "places.id,places.displayName,places.formattedAddress,places.location,"
    "places.rating,places.userRatingCount,places.googleMapsUri,places.websiteUri,"
    "places.nationalPhoneNumber,places.primaryTypeDisplayName"
)

class GooglePlacesDiscoveryProvider(DiscoveryProvider):
    def __init__(self, api_key: Optional[str] = None, http_client: Optional[httpx.AsyncClient] = None):
        self.api_key = api_key or settings.GOOGLE_PLACES_API_KEY or ""
        self._external_client = http_client
        self._client: Optional[httpx.AsyncClient] = http_client

    @property
    def provider_name(self) -> str:
        return "google_places"

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=float(getattr(settings, "GOOGLE_PLACES_TIMEOUT_SECONDS", 20.0)))
        return self._client

    async def discover(
        self,
        query: Optional[str] = None,
        location: Optional[str] = None,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
        radius: Optional[int] = None,
        category: Optional[str] = None,
    ) -> List[DiscoveryCandidateSchema]:
        if not self.api_key:
            logger.warning("GooglePlacesDiscoveryProvider called without GOOGLE_PLACES_API_KEY")
            return []

        search_parts = []
        if query and query.strip():
            search_parts.append(query.strip())
        if category and category.strip() and category.lower() not in (query or "").lower():
            search_parts.append(category.strip())
        if location and location.strip():
            loc = location.strip()
            q_lower = (query or "").lower()
            if " in " not in q_lower and " near " not in q_lower:
                search_parts.append(f"near {loc}")
            else:
                search_parts.append(loc)

        text_query = " ".join(search_parts).strip() or "businesses"

        payload = {
            "textQuery": text_query,
            "pageSize": 20
        }

        client = await self._get_client()

        # If coordinates are missing but a location is specified, geocode the location to establish circle center
        if (latitude is None or longitude is None) and location and location.strip():
            try:
                geo_resp = await client.post(
                    f"{PLACES_API_BASE_URL}/places:searchText",
                    headers={"X-Goog-Api-Key": self.api_key, "X-Goog-FieldMask": "places.location"},
                    json={"textQuery": location.strip(), "pageSize": 1}
                )
                if geo_resp.status_code == 200:
                    geo_places = geo_resp.json().get("places", [])
                    if geo_places and "location" in geo_places[0]:
                        latitude = geo_places[0]["location"].get("latitude")
                        longitude = geo_places[0]["location"].get("longitude")
            except Exception as e:
                logger.debug("Could not resolve location coordinates for '%s': %s", location, e)

        # Convert radius from kilometers to meters (if <= 100, treat as km)
        if radius and radius > 0:
            radius_meters = float(radius) * 1000.0 if radius <= 100 else float(radius)
        else:
            radius_meters = 10000.0 # Default 10km

        radius_meters = min(radius_meters, 50000.0) # Google Places API cap is 50,000 meters

        if latitude is not None and longitude is not None:
            payload["locationBias"] = {
                "circle": {
                    "center": {"latitude": latitude, "longitude": longitude},
                    "radius": radius_meters
                }
            }

        headers = {
            "X-Goog-Api-Key": self.api_key,
            "X-Goog-FieldMask": DISCOVERY_FIELD_MASK
        }

        client = await self._get_client()
        try:
            response = await client.post(
                f"{PLACES_API_BASE_URL}/places:searchText",
                headers=headers,
                json=payload
            )
            response.raise_for_status()
            data = response.json()
        except Exception as e:
            logger.exception("Failed to query Google Places searchText API")
            raise e

        places = data.get("places", [])
        candidates: List[DiscoveryCandidateSchema] = []

        for p in places:
            place_id = p.get("id")
            name = (p.get("displayName") or {}).get("text")
            if not name:
                continue

            loc_coords = p.get("location") or {}
            category_text = (p.get("primaryTypeDisplayName") or {}).get("text") or category

            candidate = DiscoveryCandidateSchema(
                source_identifier=place_id,
                source_url=p.get("googleMapsUri") or (f"https://www.google.com/maps/place/?q=place_id:{place_id}" if place_id else None),
                business_name=name,
                category=category_text,
                address=p.get("formattedAddress"),
                latitude=loc_coords.get("latitude"),
                longitude=loc_coords.get("longitude"),
                rating=float(p.get("rating")) if p.get("rating") is not None else None,
                review_count=int(p.get("userRatingCount")) if p.get("userRatingCount") is not None else None,
                phone=p.get("nationalPhoneNumber"),
                website=p.get("websiteUri")
            )
            candidates.append(candidate)

        return candidates

    async def close(self):
        if self._client and not self._external_client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

