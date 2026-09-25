import logging
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

    async def _init_browser(self):
        if not self._initialized:
            self.page = await self.browser_manager.start()
            self.navigator = ProfileNavigator(self.page)
            self._initialized = True

    async def scrape(self, target_identifier: str) -> ScrapeResult:
        """
        target_identifier here should be the Google Maps URL
        """
        result = ScrapeResult()
        
        try:
            await self._init_browser()
            
            nav_success = await self.navigator.navigate_to_updates(target_identifier)
            
            # Get HTML and parse
            html = await self.page.content()
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
                
        except Exception as e:
            logger.exception("Unexpected error during Google Maps scrape")
            result.status = "ERROR"
            result.error_message = str(e)
            
        return result

    async def close(self):
        await self.browser_manager.stop()
        self._initialized = False
