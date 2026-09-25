from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import select
from .base import BaseRepository
from app.models.profile import BusinessProfile

class BusinessProfileRepository(BaseRepository[BusinessProfile]):
    def __init__(self, session: Session):
        super().__init__(BusinessProfile, session)

    def get_by_name(self, name: str) -> Optional[BusinessProfile]:
        stmt = select(BusinessProfile).where(BusinessProfile.business_name == name)
        return self.session.scalar(stmt)
