from .base import DiscoveryProvider
from app.schemas.discovery import DiscoveryCandidateSchema
from typing import List
from app.providers.places import GooglePlacesClient
from app.core.config import settings

class GoogleMapsDiscoveryProvider(DiscoveryProvider):
    def __init__(self, places_client: GooglePlacesClient | None = None):
        self.places_client = places_client or GooglePlacesClient(
            settings.GOOGLE_PLACES_API_KEY,
            timeout_seconds=settings.GOOGLE_PLACES_TIMEOUT_SECONDS,
            max_search_pages=settings.GOOGLE_PLACES_MAX_SEARCH_PAGES,
        )

    @property
    def provider_name(self) -> str:
        return "google_places"

    async def discover(self, query: str = None, location: str = None, latitude: float = None, longitude: float = None, radius: int = None, category: str = None) -> List[DiscoveryCandidateSchema]:
        places = await self.places_client.search_businesses(
            query=query,
            location=location,
            category=category,
            latitude=latitude,
            longitude=longitude,
            radius_km=radius,
            max_results=20,
        )
        candidates = []
        for place in places:
            location_data = place.get("location") or {}
            candidates.append(
                DiscoveryCandidateSchema(
                    source_identifier=place.get("id"),
                    source_url=place.get("googleMapsUri"),
                    business_name=(place.get("displayName") or {}).get("text") or "Unknown business",
                    category=(place.get("primaryTypeDisplayName") or {}).get("text"),
                    address=place.get("formattedAddress"),
                    latitude=location_data.get("latitude"),
                    longitude=location_data.get("longitude"),
                    rating=place.get("rating"),
                    review_count=place.get("userRatingCount"),
                    phone=place.get("nationalPhoneNumber"),
                    website=place.get("websiteUri"),
                )
            )
        return candidates
        
    async def close(self):
        return None
