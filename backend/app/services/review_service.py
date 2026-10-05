import logging
from sqlalchemy.orm import Session
from app.models.review import ReviewIntelligence
from app.models.project import Project
from app.models.business import BusinessProfile
import httpx
from app.core.config import settings

logger = logging.getLogger(__name__)

class ReviewService:
    def __init__(self, db: Session, ai_provider):
        self.db = db
        self.ai_provider = ai_provider

    async def analyze_project_reviews(self, project_id: str) -> ReviewIntelligence:
        project = self.db.query(Project).filter(Project.id == project_id).first()
        if not project:
            raise ValueError("Project not found")

        business_id = project.own_business_id
        if not business_id:
            raise ValueError("Project has no own business configured")

        business = self.db.query(BusinessProfile).filter(BusinessProfile.id == business_id).first()
        
        # In a real scenario, use Places API. Using mock if no API key.
        api_key = getattr(settings, "GOOGLE_PLACES_API_KEY", None)
        if not api_key:
            raise ValueError("Review provider not configured (missing GOOGLE_PLACES_API_KEY)")
            
        return None
