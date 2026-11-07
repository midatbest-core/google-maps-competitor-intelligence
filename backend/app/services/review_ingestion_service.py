import hashlib
import logging
from typing import Optional
from sqlalchemy.orm import Session
from app.models.review import Review
from app.repositories.review_repo import ReviewRepository
from app.scraper.schemas import ExtractedReview

logger = logging.getLogger(__name__)

class ReviewIngestResult:
    def __init__(self, status: str, review_id: Optional[str] = None):
        self.status = status # "NEW_REVIEW", "DUPLICATE", "FAILED"
        self.review_id = review_id

class ReviewIngestionService:
    def __init__(self, db: Session, repo: Optional[ReviewRepository] = None):
        self.db = db
        self.repo = repo or ReviewRepository(db)

    def ingest_review(self, business_id: str, review_data: ExtractedReview) -> ReviewIngestResult:
        try:
            # Deterministic fingerprinting
            raw_fp_key = f"{business_id}|{review_data.author_name or 'anon'}|{review_data.rating or 0}|{(review_data.text or '')[:80]}"
            fingerprint = hashlib.sha256(raw_fp_key.encode("utf-8")).hexdigest()

            # 1. Deduplication check by fingerprint
            existing = self.repo.get_by_fingerprint(business_id, fingerprint)
            if existing:
                return ReviewIngestResult(status="DUPLICATE", review_id=existing.id)

            # 2. Deduplication check by source_id if present
            if review_data.source_id:
                existing_source = self.repo.get_by_source_id(business_id, review_data.source_id)
                if existing_source:
                    return ReviewIngestResult(status="DUPLICATE", review_id=existing_source.id)

            # Heuristic sentiment classification if not assigned
            sentiment = review_data.sentiment
            if not sentiment and review_data.rating is not None:
                if review_data.rating >= 4.0:
                    sentiment = "POSITIVE"
                elif review_data.rating <= 2.0:
                    sentiment = "NEGATIVE"
                else:
                    sentiment = "NEUTRAL"

            review = Review(
                business_id=business_id,
                source=review_data.source,
                source_id=review_data.source_id,
                author_name=review_data.author_name,
                author_photo_url=review_data.author_photo_url,
                rating=review_data.rating,
                text=review_data.text,
                language=review_data.language,
                published_at=review_data.published_at,
                relative_time_description=review_data.relative_time_description,
                response_text=review_data.response_text,
                response_date=review_data.response_date,
                sentiment=sentiment,
                aspects=review_data.aspects or [],
                fingerprint=fingerprint
            )

            self.db.add(review)
            self.db.commit()
            self.db.refresh(review)

            return ReviewIngestResult(status="NEW_REVIEW", review_id=review.id)

        except Exception as e:
            logger.exception(f"Failed to ingest review for business {business_id}: {e}")
            self.db.rollback()
            return ReviewIngestResult(status="FAILED")

