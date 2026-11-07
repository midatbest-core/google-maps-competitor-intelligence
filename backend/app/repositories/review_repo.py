from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import select, func, desc
from .base import BaseRepository
from app.models.review import Review

class ReviewRepository(BaseRepository[Review]):
    def __init__(self, session: Session):
        super().__init__(Review, session)

    def get_by_fingerprint(self, business_id: str, fingerprint: str) -> Optional[Review]:
        stmt = select(Review).where(
            Review.business_id == business_id,
            Review.fingerprint == fingerprint
        )
        return self.session.scalar(stmt)

    def get_by_source_id(self, business_id: str, source_id: str) -> Optional[Review]:
        stmt = select(Review).where(
            Review.business_id == business_id,
            Review.source_id == source_id
        )
        return self.session.scalar(stmt)

    def list_by_businesses(
        self,
        business_ids: List[str],
        skip: int = 0,
        limit: int = 50,
        sentiment: Optional[str] = None
    ) -> List[Review]:
        if not business_ids:
            return []
        query = select(Review).where(Review.business_id.in_(business_ids))
        if sentiment:
            query = query.where(Review.sentiment == sentiment)
        query = query.order_by(Review.published_at.desc().nulls_last(), Review.created_at.desc()).offset(skip).limit(limit)
        return list(self.session.scalars(query).all())

    def count_by_businesses(self, business_ids: List[str], sentiment: Optional[str] = None) -> int:
        if not business_ids:
            return 0
        query = select(func.count(Review.id)).where(Review.business_id.in_(business_ids))
        if sentiment:
            query = query.where(Review.sentiment == sentiment)
        return self.session.scalar(query) or 0
