from .base import DiscoveryProvider
from app.schemas.discovery import DiscoveryCandidateSchema
from typing import List

class FakeDiscoveryProvider(DiscoveryProvider):
    def __init__(self, should_fail: bool = False, candidates: List[DiscoveryCandidateSchema] = None):
        self.should_fail = should_fail
        self.candidates = candidates or [
            DiscoveryCandidateSchema(
                source_identifier="fake_id_1",
                business_name="Fake Cafe 1",
                category="Cafe",
                address="123 Fake St",
                rating=4.5,
                review_count=100
            ),
            DiscoveryCandidateSchema(
                source_identifier="fake_id_2",
                business_name="Fake Cafe 2",
                category="Cafe",
                address="456 Fake St",
                rating=4.0,
                review_count=50
            )
        ]

    @property
    def provider_name(self) -> str:
        return "fake_discovery"

    async def discover(self, query: str = None, location: str = None, latitude: float = None, longitude: float = None, radius: int = None, category: str = None) -> List[DiscoveryCandidateSchema]:
        if self.should_fail:
            raise Exception("Fake discovery provider failure")
        return self.candidates
        
    async def close(self):
        pass
