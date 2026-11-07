import logging
from typing import Optional
from sqlalchemy.orm import Session
from app.core.config import settings
from app.models.profile import BusinessProfile
from app.providers.places.google import GooglePlacesClient
from app.scraper.google_maps.review_scraper import GoogleMapsReviewScraper
from app.scraper.gosom import GosomScraperAdapter
from app.scraper.schemas import ExtractedReview
from app.services.review_ingestion_service import ReviewIngestionService

logger = logging.getLogger(__name__)

class ReviewCollectionSummary:
    def __init__(self):
        self.reviews_discovered = 0
        self.new_reviews = 0
        self.duplicates_skipped = 0
        self.status = "SUCCESS" # "SUCCESS", "NO_DATA", "PARTIAL_SUCCESS", "FAILED"
        self.error_message: Optional[str] = None

class ReviewCollectorService:
    def __init__(
        self,
        db: Session,
        places_client: Optional[GooglePlacesClient] = None,
        review_scraper: Optional[GoogleMapsReviewScraper] = None,
        gosom_adapter: Optional[GosomScraperAdapter] = None,
        ingestion_service: Optional[ReviewIngestionService] = None,
    ):
        self.db = db
        self.places_client = places_client or (
            GooglePlacesClient(
                settings.GOOGLE_PLACES_API_KEY,
                timeout_seconds=settings.GOOGLE_PLACES_TIMEOUT_SECONDS,
            )
            if getattr(settings, "GOOGLE_PLACES_API_KEY", None)
            else None
        )
        self.review_scraper = review_scraper
        self.gosom_adapter = gosom_adapter or GosomScraperAdapter()
        self.ingestion_service = ingestion_service or ReviewIngestionService(db)

    async def collect_reviews_for_business(
        self,
        business: BusinessProfile,
        max_browser_reviews: int = 50
    ) -> ReviewCollectionSummary:
        summary = ReviewCollectionSummary()
        collected_reviews: list[ExtractedReview] = []

        # 1. Try Browser-Based Scraper if URL is available
        if business.google_maps_url:
            # Check if gosom is configured first
            if self.gosom_adapter.is_available():
                logger.info(f"Using gosom runner for {business.business_name}")
                gosom_res = await self.gosom_adapter.scrape_reviews(business.google_maps_url)
                if gosom_res.status == "SUCCESS":
                    collected_reviews.extend(gosom_res.reviews)

            # If no reviews yet from gosom, use native Playwright review scraper
            if not collected_reviews:
                scraper = self.review_scraper or GoogleMapsReviewScraper()
                try:
                    logger.info(f"Using native Playwright review scraper for {business.business_name}")
                    scrape_res = await scraper.scrape_reviews(business.google_maps_url, max_reviews=max_browser_reviews)
                    if scrape_res.status == "SUCCESS":
                        collected_reviews.extend(scrape_res.reviews)
                    elif scrape_res.status == "VERIFICATION_REQUIRED":
                        summary.status = "VERIFICATION_REQUIRED"
                        summary.error_message = scrape_res.error_message
                        return summary
                finally:
                    if not self.review_scraper:
                        await scraper.close()

        # 2. Try Google Places API (if configured)
        if self.places_client and getattr(settings, "GOOGLE_PLACES_API_KEY", None):
            try:
                places_res = await self.places_client.fetch_reviews(
                    business_name=business.business_name,
                    address=business.address,
                    canonical_source_id=business.canonical_source_id,
                    google_maps_url=business.google_maps_url
                )
                for pr in places_res.reviews:
                    rating = pr.get("rating")
                    collected_reviews.append(ExtractedReview(
                        source_id=pr.get("name"),
                        author_name=pr.get("authorAttribution", {}).get("displayName") or pr.get("author_name"),
                        author_photo_url=pr.get("authorAttribution", {}).get("photoUri"),
                        rating=float(rating) if rating is not None else None,
                        text=pr.get("text", {}).get("text") if isinstance(pr.get("text"), dict) else pr.get("text"),
                        relative_time_description=pr.get("relativePublishTimeDescription"),
                        source="google_places_api"
                    ))
            except Exception as e:
                logger.warning(f"Google Places API review fetch failed for {business.business_name}: {e}")

        summary.reviews_discovered = len(collected_reviews)

        if not collected_reviews:
            if summary.status != "VERIFICATION_REQUIRED":
                summary.status = "NO_DATA"
            return summary

        # 3. Ingest collected reviews into database
        for r_data in collected_reviews:
            ingest_res = self.ingestion_service.ingest_review(business.id, r_data)
            if ingest_res.status == "NEW_REVIEW":
                summary.new_reviews += 1
            elif ingest_res.status == "DUPLICATE":
                summary.duplicates_skipped += 1

        summary.status = "SUCCESS"
        return summary

