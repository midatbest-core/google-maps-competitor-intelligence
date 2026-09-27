from .base import DiscoveryProvider
from .fake import FakeDiscoveryProvider
from .google_maps import GoogleMapsDiscoveryProvider
from app.core.config import settings

def get_discovery_provider() -> DiscoveryProvider:
    if settings.APP_ENV == "test" or getattr(settings, "DISCOVERY_PROVIDER", "fake") == "fake":
        return FakeDiscoveryProvider()
    return GoogleMapsDiscoveryProvider()
