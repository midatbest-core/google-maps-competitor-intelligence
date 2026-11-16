import logging
from playwright.async_api import async_playwright, Playwright, Browser, BrowserContext, Page
from app.core.config import settings

logger = logging.getLogger(__name__)

CHROMIUM_ARGS = [
    "--disable-blink-features=AutomationControlled",
    "--no-sandbox",
    "--disable-setuid-sandbox",
    "--disable-dev-shm-usage",
    "--disable-gpu",
    "--disable-extensions",
    "--no-first-run",
    "--disable-background-networking",
    "--disable-default-apps",
    "--mute-audio",
]


class BrowserManager:
    def __init__(self):
        self.playwright: Playwright | None = None
        self.browser: Browser | None = None
        self.context: BrowserContext | None = None

    async def start(self) -> Page:
        """Starts Playwright, launches Chromium with container-safe flags, and returns a new page."""
        if not self.playwright:
            self.playwright = await async_playwright().start()

        headless = settings.SCRAPER_HEADLESS
        if not self.browser or not self.browser.is_connected():
            self.browser = await self.playwright.chromium.launch(
                headless=headless,
                args=CHROMIUM_ARGS
            )

        if not self.context:
            self.context = await self.browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                viewport={"width": 1280, "height": 800},
                ignore_https_errors=True,
            )

        page = await self.context.new_page()
        page.set_default_timeout(settings.SCRAPER_TIMEOUT * 1000)
        return page

    async def new_page(self) -> Page:
        """Creates a fresh page in the active browser context."""
        try:
            if not self.context or not self.browser or not self.browser.is_connected():
                return await self.start()
            page = await self.context.new_page()
            page.set_default_timeout(settings.SCRAPER_TIMEOUT * 1000)
            return page
        except Exception as e:
            logger.warning(f"Failed to create new page, restarting browser: {e}")
            await self.stop()
            return await self.start()

    async def close_page(self, page: Page | None):
        """Safely closes a page if open."""
        if page:
            try:
                if not page.is_closed():
                    await page.close()
            except Exception as e:
                logger.debug(f"Error closing page: {e}")

    async def stop(self):
        """Safely tears down context, browser, and playwright instances."""
        if self.context:
            try:
                await self.context.close()
            except Exception:
                pass
            self.context = None

        if self.browser:
            try:
                await self.browser.close()
            except Exception:
                pass
            self.browser = None

        if self.playwright:
            try:
                await self.playwright.stop()
            except Exception:
                pass
            self.playwright = None
