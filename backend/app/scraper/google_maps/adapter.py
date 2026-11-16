import logging
import asyncio
from bs4 import BeautifulSoup
from app.scraper.base import SourceAdapter
from app.scraper.schemas import ScrapeResult, ExtractionFailure
from app.scraper.google_maps.browser import BrowserManager
from app.scraper.google_maps.navigator import ProfileNavigator
from app.scraper.google_maps.locator import PostLocator
from app.scraper.google_maps.extractor import PostExtractor
from app.scraper.google_maps.captcha import CaptchaDetector
from app.scraper.google_maps.normalizer import Normalizer
from app.scraper.google_maps.identity import IdentityGenerator

logger = logging.getLogger(__name__)

class GoogleMapsAdapter(SourceAdapter):
    def __init__(self, browser_manager: BrowserManager | None = None):
        self.browser_manager = browser_manager or BrowserManager()
        self._initialized = False
        self.page = None

    async def _init_browser(self):
        if not self._initialized:
            self.page = await self.browser_manager.start()
            self.navigator = ProfileNavigator(self.page)
            self._initialized = True

    async def scrape(self, target_identifier: str) -> ScrapeResult:
        """
        target_identifier here should be the Google Maps URL.
        Uses an isolated page per scrape to prevent memory leaks and DOM pollution across businesses.
        """
        result = ScrapeResult()
        page = None
        
        try:
            # Open a fresh isolated page
            page = await self.browser_manager.new_page()
            self.page = page
            navigator = ProfileNavigator(page)
            self.navigator = navigator
            
            nav_success = await navigator.navigate_to_updates(target_identifier)
            
            # Get HTML and parse
            html = await page.content()
            soup = BeautifulSoup(html, 'html.parser')
            
            # 1. Check for Captcha / Verification
            if CaptchaDetector.detect(soup):
                logger.warning(f"Verification required detected for {target_identifier}")
                result.status = "VERIFICATION_REQUIRED"
                result.error_message = "CAPTCHA or verification wall detected"
                return result
                
            if not nav_success:
                # Might just mean no posts exist
                result.status = "NO_DATA"
                return result
                
            # 2. Locate post containers
            containers = PostLocator.locate(soup)
            
            if not containers:
                result.status = "NO_DATA"
                return result
                
            # 3. Extract and normalize
            for idx, container in enumerate(containers):
                try:
                    post = PostExtractor.extract(container)
                    post = Normalizer.normalize(post)
                    post.fingerprint = IdentityGenerator.generate_fingerprint(post)
                    result.posts.append(post)
                except Exception as e:
                    logger.exception(f"Failed to extract post {idx}")
                    result.failures.append(ExtractionFailure(
                        reason=str(e),
                        raw_content_preview=str(container)[:200]
                    ))
                    
            if not result.posts and result.failures:
                result.status = "ERROR"
                result.error_message = "Failed to extract any posts"
            else:
                result.status = "SUCCESS"
                
        except asyncio.TimeoutError:
            logger.warning(f"Timeout while scraping {target_identifier}")
            result.status = "ERROR"
            result.error_message = f"Timeout after scraping attempt for {target_identifier}"
        except Exception as e:
            logger.exception("Unexpected error during Google Maps scrape")
            result.status = "ERROR"
            result.error_message = str(e)
        finally:
            if self.page is page:
                self.page = None
            if getattr(self, "navigator", None) is navigator:
                self.navigator = None
            if page:
                await self.browser_manager.close_page(page)
            
        return result

    async def close(self):
        await self.browser_manager.stop()
        self.page = None
        self._initialized = False
