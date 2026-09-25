import logging
from playwright.async_api import Page, TimeoutError

logger = logging.getLogger(__name__)

class ProfileNavigator:
    def __init__(self, page: Page):
        self.page = page

    async def navigate_to_updates(self, target_url: str) -> bool:
        """
        Navigates to the given Google Maps URL and attempts to open the Updates/Posts tab.
        Returns True if successful, False if it fails (e.g. timeout, no tab).
        """
        try:
            logger.info(f"Navigating to {target_url}")
            # wait_until domcontentloaded is usually enough for the basic structure
            await self.page.goto(target_url, wait_until="domcontentloaded")
            
            # Wait for the main panel to load
            await self.page.wait_for_selector('div[role="main"]', timeout=10000)
            
            # Scroll to trigger lazy loading if necessary, though clicking the tab is better
            # Try to find the "Updates" or "Posts" tab. We use a generic text selector for robustness,
            # or data-item-id if available.
            # Using multiple strategies.
            tab_selectors = [
                'button[aria-label*="Updates"]',
                'button[aria-label*="Posts"]',
                'div.Gpq6fc:has-text("Updates")',
                'div.Gpq6fc:has-text("Posts")'
            ]
            
            for selector in tab_selectors:
                try:
                    tab = await self.page.wait_for_selector(selector, timeout=2000)
                    if tab:
                        await tab.click()
                        # Wait for posts container to load
                        await self.page.wait_for_selector('div[data-post-id], div.ODSEW-BN9H-post', timeout=5000)
                        return True
                except TimeoutError:
                    continue
            
            logger.warning("Could not find Updates tab via explicit click. It might not exist or the page layout changed.")
            return False
            
        except TimeoutError:
            logger.error("Timeout during navigation")
            return False
        except Exception as e:
            logger.exception("Unexpected error during navigation")
            return False
