from .base import DiscoveryProvider
from .fake import FakeDiscoveryProvider
from .google_maps import GoogleMapsDiscoveryProvider
from .google_places import GooglePlacesDiscoveryProvider
from app.core.config import settings

def get_discovery_provider() -> DiscoveryProvider:
    provider_name = getattr(settings, "DISCOVERY_PROVIDER", "").lower()
    
    if settings.APP_ENV == "test" or provider_name == "fake":
        return FakeDiscoveryProvider()
        
    if provider_name == "google_places" or (not provider_name and bool(settings.GOOGLE_PLACES_API_KEY)):
        return GooglePlacesDiscoveryProvider()
        
    if provider_name == "google_maps":
        return GoogleMapsDiscoveryProvider()
        
    if bool(settings.GOOGLE_PLACES_API_KEY):
        return GooglePlacesDiscoveryProvider()
        
    return FakeDiscoveryProvider()
