import logging
from playwright.async_api import async_playwright, Playwright, Browser, BrowserContext, Page
from app.core.config import settings

logger = logging.getLogger(__name__)

class BrowserManager:
    def __init__(self):
        self.playwright: Playwright | None = None
        self.browser: Browser | None = None
        self.context: BrowserContext | None = None

    async def start(self) -> Page:
        self.playwright = await async_playwright().start()
        
        headless = settings.SCRAPER_HEADLESS
        # In a robust implementation you could use persistent contexts if profile_dir is configured
        self.browser = await self.playwright.chromium.launch(
            headless=headless,
            args=["--disable-blink-features=AutomationControlled"]
        )
        self.context = await self.browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = await self.context.new_page()
        page.set_default_timeout(settings.SCRAPER_TIMEOUT * 1000)
        return page

    async def stop(self):
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
