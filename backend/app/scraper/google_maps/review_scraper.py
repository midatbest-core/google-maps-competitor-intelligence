import asyncio
import hashlib
import logging
import re
from datetime import datetime, timezone
from bs4 import BeautifulSoup
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

from app.scraper.schemas import ExtractedReview, ExtractionFailure, ReviewScrapeResult
from app.scraper.google_maps.browser import BrowserManager
from app.scraper.google_maps.captcha import CaptchaDetector

logger = logging.getLogger(__name__)

_REVIEW_TAB_SELECTORS = [
    'button[aria-label*="Reviews"]',
    'button[aria-label*="reviews"]',
    '[role="tab"]:has-text("Reviews")',
    'button:has-text("Reviews")',
    'div.Gpq6fc:has-text("Reviews")',
]

_STAR_RATING_PATTERN = re.compile(r"([0-5](?:\.[0-9])?)\s*(?:stars?|étoiles?|sterne?)?", re.IGNORECASE)


class GoogleMapsReviewScraper:
    def __init__(self, browser_manager: BrowserManager | None = None):
        self.browser_manager = browser_manager or BrowserManager()
        self._initialized = False

    async def _init_browser(self):
        if not self._initialized:
            self.page = await self.browser_manager.start()
            self._initialized = True

    async def scrape_reviews(self, target_url: str, max_reviews: int = 50) -> ReviewScrapeResult:
        result = ReviewScrapeResult()

        try:
            await self._init_browser()
            logger.info(f"Navigating to {target_url} for reviews extraction (target max: {max_reviews})")
            await self.page.goto(target_url, wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(2)

            # Check CAPTCHA
            html = await self.page.content()
            soup = BeautifulSoup(html, "html.parser")
            if CaptchaDetector.detect(soup):
                logger.warning(f"CAPTCHA or verification detected for {target_url}")
                result.status = "VERIFICATION_REQUIRED"
                result.error_message = "CAPTCHA or verification wall detected"
                return result

            # Click Reviews Tab
            tab_clicked = False
            for sel in _REVIEW_TAB_SELECTORS:
                try:
                    elem = self.page.locator(sel).first
                    if await elem.count() > 0 and await elem.is_visible():
                        logger.info(f"Clicking reviews tab with selector: {sel}")
                        await elem.click()
                        tab_clicked = True
                        await asyncio.sleep(2)
                        break
                except Exception:
                    continue

            # If no tab clicked, check if reviews feed is already visible
            feed_locator = self.page.locator('div[role="feed"]').first
            feed_count = await feed_locator.count()

            if not tab_clicked and feed_count == 0:
                logger.info(f"No reviews tab or feed found on {target_url}")
                result.status = "NO_DATA"
                return result

            # Scroll the review feed to load up to max_reviews
            try:
                consecutive_stalls = 0
                last_card_count = 0
                max_scroll_cycles = max(15, min(max_reviews // 2, 40))

                for cycle in range(max_scroll_cycles):
                    current_cards = await self.page.locator('div.jftiEf, div[data-review-id], div.WMbnJf').count()
                    if current_cards >= max_reviews:
                        logger.info(f"Reached target review count ({current_cards}/{max_reviews}) at cycle {cycle}")
                        break

                    if current_cards == last_card_count and current_cards > 0:
                        consecutive_stalls += 1
                        if consecutive_stalls >= 4:
                            logger.info(f"Feed stopped loading new reviews after {current_cards} items.")
                            break
                    else:
                        consecutive_stalls = 0
                        last_card_count = current_cards

                    # Scroll feed to bottom
                    scrolled = await self.page.evaluate('''
                        () => {
                            const card = document.querySelector('div.jftiEf, div[data-review-id], div.WMbnJf');
                            let el = card ? card.parentElement : null;
                            while (el && el !== document.body) {
                                const style = window.getComputedStyle(el);
                                if ((style.overflowY === 'auto' || style.overflowY === 'scroll') && el.scrollHeight > el.clientHeight) {
                                    el.scrollTop = el.scrollHeight;
                                    return true;
                                }
                                el = el.parentElement;
                            }
                            const candidates = document.querySelectorAll('div[role="feed"], div.m6QErb, div[tabindex="-1"]');
                            for (const c of candidates) {
                                if (c.scrollHeight > c.clientHeight && c.clientHeight > 200) {
                                    c.scrollTop = c.scrollHeight;
                                    return true;
                                }
                            }
                            return false;
                        }
                    ''')

                    panel = self.page.locator('div.jftiEf, div[role="feed"], div[role="main"]').first
                    try:
                        box = await panel.bounding_box()
                        if box:
                            await self.page.mouse.move(box["x"] + box["width"] * 0.5, box["y"] + box["height"] * 0.5)
                            await self.page.mouse.wheel(0, 2000)
                    except Exception:
                        pass

                    await asyncio.sleep(1.2)
            except Exception as e:
                logger.warning(f"Error while scrolling reviews feed: {e}")

            # Expand 'More' buttons if present
            try:
                more_buttons = self.page.locator('button.w8nwRe, button:has-text("More"), button[aria-label*="See more"]')
                btn_count = await more_buttons.count()
                for i in range(min(btn_count, 50)):
                    try:
                        btn = more_buttons.nth(i)
                        if await btn.is_visible():
                            await btn.click(timeout=500)
                    except Exception:
                        pass
            except Exception:
                pass

            # Extract review items from DOM
            html = await self.page.content()
            soup = BeautifulSoup(html, "html.parser")

            # Look for review cards
            review_cards = soup.select("div.jftiEf, div[data-review-id], div.WMbnJf")
            if not review_cards:
                # Fallback: look for review containers with author and text
                review_cards = soup.select('div[class*="review"]')

            logger.info(f"Found {len(review_cards)} review card elements")

            for idx, card in enumerate(review_cards[:max_reviews]):
                try:
                    review = self._parse_review_card(card)
                    if review:
                        result.reviews.append(review)
                except Exception as e:
                    logger.exception(f"Error parsing review card {idx}: {e}")
                    result.failures.append(ExtractionFailure(
                        reason=str(e),
                        raw_content_preview=str(card)[:200]
                    ))

            if not result.reviews and result.failures:
                result.status = "ERROR"
                result.error_message = "Failed to parse any reviews from page"
            elif not result.reviews:
                result.status = "NO_DATA"
            else:
                result.status = "SUCCESS"

        except PlaywrightTimeoutError as e:
            logger.warning(f"Timeout extracting reviews for {target_url}: {e}")
            result.status = "ERROR"
            result.error_message = f"Navigation timeout: {str(e)}"
        except Exception as e:
            logger.exception(f"Unexpected error in review scraping: {e}")
            result.status = "ERROR"
            result.error_message = str(e)

        return result

    def _parse_review_card(self, card) -> ExtractedReview | None:
        # 1. Author Name
        author_elem = card.select_one("div.d4r55, button.alPpvf, .WNxFhc, [class*='author']")
        author_name = author_elem.get_text(strip=True) if author_elem else None

        # 2. Rating
        rating = None
        rating_elem = card.select_one("span.kvMYJc, [role='img'][aria-label*='star'], [role='img'][aria-label*='stars']")
        if rating_elem and rating_elem.get("aria-label"):
            match = _STAR_RATING_PATTERN.search(rating_elem["aria-label"])
            if match:
                try:
                    rating = float(match.group(1))
                except ValueError:
                    pass

        # 3. Review Text
        text_elem = card.select_one("span.wiI7pd, span.raw_text, div.MyEnff")
        text = text_elem.get_text(strip=True) if text_elem else None

        # 4. Relative Date
        date_elem = card.select_one("span.rsqaWe, span[class*='date']")
        relative_date = date_elem.get_text(strip=True) if date_elem else None

        # 5. Owner Response
        response_elem = card.select_one("div.CDe7pd, div[class*='owner-response']")
        response_text = None
        if response_elem:
            resp_body = response_elem.select_one("div.wiI7pd, [class*='text']")
            response_text = resp_body.get_text(strip=True) if resp_body else response_elem.get_text(strip=True)

        # 6. Source ID
        source_id = card.get("data-review-id")

        # Must have at least author, rating, or text
        if not author_name and rating is None and not text:
            return None

        # Determine simple heuristic sentiment
        sentiment = "NEUTRAL"
        if rating is not None:
            if rating >= 4.0:
                sentiment = "POSITIVE"
            elif rating <= 2.0:
                sentiment = "NEGATIVE"

        # Deduplication Fingerprint
        raw_key = f"{author_name or 'unknown'}|{rating or 0}|{(text or '')[:100]}"
        fingerprint = hashlib.sha256(raw_key.encode("utf-8")).hexdigest()

        return ExtractedReview(
            source_id=source_id,
            author_name=author_name,
            rating=rating,
            text=text,
            relative_time_description=relative_date,
            response_text=response_text,
            sentiment=sentiment,
            source="browser_scraper",
            fingerprint=fingerprint
        )

    async def close(self):
        await self.browser_manager.stop()
        self._initialized = False

