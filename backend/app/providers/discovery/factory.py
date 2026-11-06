from .base import DiscoveryProvider
from .fake import FakeDiscoveryProvider
from .google_maps import GoogleMapsDiscoveryProvider
from app.core.config import settings

def get_discovery_provider() -> DiscoveryProvider:
    if settings.APP_ENV == "test" or settings.DISCOVERY_PROVIDER == "fake":
        return FakeDiscoveryProvider()
    if settings.DISCOVERY_PROVIDER == "google_places":
        return GoogleMapsDiscoveryProvider()
    raise ValueError("Unsupported DISCOVERY_PROVIDER configured")
