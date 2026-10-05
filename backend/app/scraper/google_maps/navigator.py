import logging
import asyncio
from playwright.async_api import Page, TimeoutError

logger = logging.getLogger(__name__)

# Selectors for post containers — used both to verify navigation succeeded
# and to detect inline-rendered posts that don't require a tab click.
_POST_CONTAINER_SELECTORS = [
    # Strategy 1 – stable data attributes (older DOM / some regions)
    '[data-post-id]',
    '[data-update-id]',
    '[data-sharing-url]',
    # Strategy 2 – known class names (current Google Maps DOM as of 2026)
    '.localPostExpanded',
    '.TrG26d',           # post body text container
    # Strategy 3 - From the owner section (current Google Maps DOM)
    '.SBD2Rc',
    '.waIsr',
    'div:has-text("From the owner") + div .SBD2Rc',
    # Strategy 4 – ARIA feed (used by some business types)
    '[role="feed"]',
    # Strategy 5 – legacy class name
    '.ODSEW-BN9H-post',
]


class ProfileNavigator:
    def __init__(self, page: Page):
        self.page = page

    async def _posts_already_visible(self) -> bool:
        """Returns True if post containers are already present in the DOM."""
        for sel in _POST_CONTAINER_SELECTORS:
            try:
                count = await self.page.locator(sel).count()
                if count > 0:
                    logger.info(f"Posts already visible via selector '{sel}' (count={count})")
                    return True
            except Exception:
                continue
        return False

    async def _try_click_updates_tab(self) -> bool:
        """
        Attempts to find and click the Updates/Posts tab using multiple selector
        strategies that reflect how Google Maps renders tabs across different
        DOM versions and regions.

        Returns True if a tab was found and clicked (regardless of whether posts
        were subsequently found — the caller checks that).
        """
        # Priority-ordered list of (selector, description) pairs.
        # Each selector targets the Updates/Posts navigation tab element.
        tab_strategies = [
            # 1. aria-label on button (most reliable when present)
            ('button[aria-label*="Updates"]',              "button[aria-label*=Updates]"),
            ('button[aria-label*="Posts"]',                "button[aria-label*=Posts]"),
            # 2. role=tab with matching inner text (current DOM)
            ('[role="tab"]:has-text("Updates")',           "role=tab has-text(Updates)"),
            ('[role="tab"]:has-text("Posts")',             "role=tab has-text(Posts)"),
            # 3. Old Gpq6fc class pattern
            ('div.Gpq6fc:has-text("Updates")',             "div.Gpq6fc Updates"),
            ('div.Gpq6fc:has-text("Posts")',               "div.Gpq6fc Posts"),
            # 4. Any clickable element whose visible text is exactly "Updates" or "Posts"
            ('text="Updates"',                             "exact text=Updates"),
            ('text="Posts"',                               "exact text=Posts"),
        ]

        for selector, description in tab_strategies:
            try:
                element = self.page.locator(selector).first
                count = await element.count()
                if count == 0:
                    continue
                logger.info(f"Found Updates tab via: {description}")
                await element.click()
                # Give the page time to load post content
                await asyncio.sleep(2)
                return True
            except Exception:
                continue

        return False

    async def _scroll_panel_for_posts(self) -> None:
        """Scrolls the left-side business panel to trigger lazy-loaded post sections."""
        try:
            panel = self.page.locator('div[role="main"]').first
            box = await panel.bounding_box()
            if box:
                cx = box["x"] + box["width"] * 0.3
                cy = box["y"] + box["height"] * 0.5
                for _ in range(8):
                    await self.page.mouse.move(cx, cy)
                    await self.page.mouse.wheel(0, 400)
                    await asyncio.sleep(0.3)
                await asyncio.sleep(1)
        except Exception:
            pass

    async def navigate_to_updates(self, target_url: str) -> bool:
        """
        Navigates to the given Google Maps business URL and attempts to surface
        the business's Updates / Posts content.

        Strategy (tried in order):
          1. Navigate and wait for the main panel.
          2. If post containers are already visible (some businesses render posts
             inline without a separate tab), return True immediately.
          3. Attempt to locate and click an Updates/Posts tab using multiple
             selector strategies.
          4. After a successful tab click, verify that post containers appeared.
          5. If no tab was found, scroll the panel to trigger lazy loading and
             check again for post containers.
          6. Return False only when no posts are found after all strategies.
        """
        try:
            logger.info(f"Navigating to: {target_url}")
            await self.page.goto(target_url, wait_until="domcontentloaded")
            await self.page.wait_for_selector('div[role="main"]', timeout=12000)

            # Step 2 – check if posts are already in the DOM
            if await self._posts_already_visible():
                return True

            # Step 3 – try to click the Updates/Posts tab
            clicked = await self._try_click_updates_tab()

            if clicked:
                # Step 4 – verify post containers appeared after the click
                if await self._posts_already_visible():
                    return True
                # Tab was there but posts didn't load (e.g. no posts yet)
                logger.info("Updates tab found and clicked, but no post containers appeared")
                return False

            # Step 5 – no tab found; scroll panel and try once more
            logger.info("No Updates tab found via selectors; scrolling panel for lazy content")
            await self._scroll_panel_for_posts()
            if await self._posts_already_visible():
                return True

            logger.warning(
                "Updates/Posts content not found after all strategies. "
                "Business may not have any posts, or the page structure has changed."
            )
            return False

        except TimeoutError:
            logger.error("Timeout while navigating to business page")
            return False
        except Exception:
            logger.exception("Unexpected error during navigation")
            return False
