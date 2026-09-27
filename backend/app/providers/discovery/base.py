import abc
from typing import List
from app.schemas.discovery import DiscoveryCandidateSchema

class DiscoveryProvider(abc.ABC):
    """Base abstraction for map discovery providers."""

    @property
    @abc.abstractmethod
    def provider_name(self) -> str:
        pass

    @abc.abstractmethod
    async def discover(self, query: str = None, location: str = None, latitude: float = None, longitude: float = None, radius: int = None, category: str = None) -> List[DiscoveryCandidateSchema]:
        """
        Discovers candidates matching the given criteria.
        """
        pass
    
    @abc.abstractmethod
    async def close(self):
        """Cleanup resources."""
        pass
