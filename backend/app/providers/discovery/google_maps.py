from .base import DiscoveryProvider
from app.schemas.discovery import DiscoveryCandidateSchema
from typing import List, Optional
from app.scraper.google_maps.browser import BrowserManager
import logging

logger = logging.getLogger(__name__)

class GoogleMapsDiscoveryProvider(DiscoveryProvider):
    def __init__(self):
        self.browser_manager: Optional[BrowserManager] = None

    @property
    def provider_name(self) -> str:
        return "google_maps"

    async def discover(self, query: str = None, location: str = None, latitude: float = None, longitude: float = None, radius: int = None, category: str = None) -> List[DiscoveryCandidateSchema]:
        search_query = ""
        if query: search_query += query
        if category and category not in search_query:
            search_query += f" {category}"
        if location:
            search_query += f" near {location}"
            
        if not search_query.strip():
            search_query = "businesses"

        self.browser_manager = BrowserManager()
        page = await self.browser_manager.start()
        candidates = []
        try:
            url = f"https://www.google.com/maps/search/{search_query.replace(' ', '+')}"
            await page.goto(url, wait_until="domcontentloaded")
            await page.wait_for_timeout(3000)
            
            elements = await page.query_selector_all('a[href*="/maps/place/"]')
            for el in elements[:10]:
                href = await el.get_attribute('href')
                name = await el.get_attribute('aria-label')
                if href and name:
                    candidates.append(DiscoveryCandidateSchema(
                        source_url=href,
                        business_name=name
                    ))
        except Exception as e:
            logger.error(f"Error in GoogleMaps discovery: {e}")
            raise e
        finally:
            if self.browser_manager:
                await self.browser_manager.stop()
                self.browser_manager = None
                
        return candidates
        
    async def close(self):
        if self.browser_manager:
            await self.browser_manager.stop()
            self.browser_manager = None
