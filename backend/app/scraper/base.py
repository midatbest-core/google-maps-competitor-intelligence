from abc import ABC, abstractmethod
from app.scraper.schemas import ScrapeResult
from typing import Optional

class SourceAdapter(ABC):
    @abstractmethod
    async def scrape(self, target_identifier: str) -> ScrapeResult:
        """
        Scrapes a target and returns a normalized ScrapeResult containing posts, failures, and status.
        """
        pass
    
    @abstractmethod
    async def close(self):
        """
        Cleans up resources (e.g. browser context).
        """
        pass
