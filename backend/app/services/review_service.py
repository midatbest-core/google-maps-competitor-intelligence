import logging
from sqlalchemy.orm import Session
from app.models.review import ReviewIntelligence
from app.models.project import Project
from app.models.profile import BusinessProfile
from app.core.config import settings
from datetime import datetime, timezone
from app.providers.places import GooglePlacesClient, PlacesReviewResult

logger = logging.getLogger(__name__)

class ReviewService:
    def __init__(
        self,
        db: Session,
        ai_provider,
        places_client: GooglePlacesClient | None = None,
        workspace=None,
    ):
        self.db = db
        self.ai_provider = ai_provider
        self.workspace = workspace
        self.places_client = places_client or GooglePlacesClient(
            settings.GOOGLE_PLACES_API_KEY,
            timeout_seconds=settings.GOOGLE_PLACES_TIMEOUT_SECONDS,
            max_search_pages=settings.GOOGLE_PLACES_MAX_SEARCH_PAGES,
        )

    async def fetch_google_reviews(self, business: BusinessProfile) -> PlacesReviewResult:
        result = await self.places_client.fetch_reviews(
            business_name=business.business_name,
            address=business.address,
            canonical_source_id=business.canonical_source_id,
            google_maps_url=business.google_maps_url,
        )

        if business.canonical_source_id != result.place_id:
            duplicate = self.db.query(BusinessProfile).filter(
                BusinessProfile.canonical_source_id == result.place_id,
                BusinessProfile.id != business.id,
            ).first()
            if duplicate:
                raise ValueError(
                    "Resolved Google Place ID is already assigned to another business"
                )
            business.canonical_source_id = result.place_id
            self.db.commit()
            self.db.refresh(business)
        return result

    async def analyze_project_reviews(self, project_id: str) -> ReviewIntelligence:
        project = self.db.query(Project).filter(Project.id == project_id).first()
        if not project or (
            self.workspace and project.workspace_id != self.workspace.id
        ):
            raise ValueError("Project not found")

        business_id = project.own_business_id
        if not business_id:
            raise ValueError("Project has no own business configured")

        business = self.db.query(BusinessProfile).filter(BusinessProfile.id == business_id).first()
        if not business:
            raise ValueError("Project's own business could not be found")

        # 1. Fetch reviews
        review_result = await self.fetch_google_reviews(business)
        reviews = review_result.reviews
        if not reviews:
            raise ValueError(
                "Google Places returned no review text for this business. "
                "Place Details currently returns at most five reviews."
            )

        # 2. Analyze with Gemini
        reviews_text = "\n---\n".join([f"Rating: {r['rating']} - {r['text']}" for r in reviews])
        prompt = "Analyze the following business reviews and provide a structured JSON response."

        parsed_result, raw_dict = await self.ai_provider.analyze_reviews(prompt, reviews_text)

        # 3. Calculate avg rating
        ratings = [r["rating"] for r in reviews if r.get("rating") is not None]
        avg_rating = review_result.average_rating
        if avg_rating is None and ratings:
            avg_rating = sum(ratings) / len(ratings)

        # 4. Save to DB
        existing = self.db.query(ReviewIntelligence).filter(
            ReviewIntelligence.project_id == project_id,
            ReviewIntelligence.business_id == business_id
        ).first()

        if existing:
            self.db.delete(existing)
            self.db.commit()

        intel = ReviewIntelligence(
            project_id=project_id,
            business_id=business_id,
            reviews_analyzed_count=len(reviews),
            overall_sentiment=parsed_result.overall_sentiment,
            positive_percentage=parsed_result.sentiment_breakdown.positive,
            neutral_percentage=parsed_result.sentiment_breakdown.neutral,
            negative_percentage=parsed_result.sentiment_breakdown.negative,
            average_rating=avg_rating,
            praise_themes=parsed_result.praise_themes,
            complaint_themes=parsed_result.complaint_themes,
            pain_points=parsed_result.pain_points,
            customer_needs=parsed_result.customer_needs,
            frequently_mentioned_services=parsed_result.frequently_mentioned_services,
            strengths=parsed_result.strengths,
            weaknesses=parsed_result.weaknesses,
            business_opportunities=parsed_result.business_opportunities,
            recommended_actions=parsed_result.recommended_actions,
            analysis_provider=self.ai_provider.provider_name,
            model_version=self.ai_provider.model_name,
            analyzed_at=datetime.now(timezone.utc)
        )
        self.db.add(intel)
        self.db.commit()
        self.db.refresh(intel)

        return intel

    def get_review_intelligence(self, project_id: str) -> ReviewIntelligence:
        query = self.db.query(ReviewIntelligence).join(
            Project,
            Project.id == ReviewIntelligence.project_id,
        ).filter(ReviewIntelligence.project_id == project_id)
        if self.workspace:
            query = query.filter(Project.workspace_id == self.workspace.id)
        return query.first()

    def get_project_reviews(
        self,
        project_id: str,
        page: int = 1,
        page_size: int = 20,
        competitor_id: str | None = None,
        sentiment: str | None = None,
        source: str | None = None,
    ):
        project = self.db.query(Project).filter_by(id=project_id).first()
        if not project or (self.workspace and project.workspace_id != self.workspace.id):
            raise ValueError("Project not found")

        from app.models.competitor import ProjectCompetitor
        from app.models.review import Review
        from app.schemas.review import ReviewResponse, ReviewListResponse
        from sqlalchemy import desc

        if competitor_id:
            comp = self.db.query(ProjectCompetitor).filter_by(project_id=project_id, business_id=competitor_id).first()
            if not comp and project.own_business_id != competitor_id:
                raise ValueError("Competitor not found in project")
            business_ids = [competitor_id]
        else:
            comp_ids = [c.business_id for c in self.db.query(ProjectCompetitor).filter_by(project_id=project_id, is_active=True).all()]
            business_ids = comp_ids
            if project.own_business_id and project.own_business_id not in business_ids:
                business_ids.append(project.own_business_id)

        if not business_ids:
            return ReviewListResponse(items=[], total=0, page=page, page_size=page_size, pages=0)

        query = self.db.query(Review).filter(Review.business_id.in_(business_ids))
        if sentiment:
            query = query.filter(Review.sentiment == sentiment.upper())
        if source:
            query = query.filter(Review.source == source)

        total = query.count()
        offset = max(0, (page - 1) * page_size)
        reviews = query.order_by(Review.published_at.desc().nulls_last(), Review.created_at.desc()).offset(offset).limit(page_size).all()

        biz_map = {b.id: b.business_name for b in self.db.query(BusinessProfile).filter(BusinessProfile.id.in_(business_ids)).all()}

        items = []
        for r in reviews:
            resp = ReviewResponse.model_validate(r)
            resp.business_name = biz_map.get(r.business_id, "Unknown")
            items.append(resp)

        pages = (total + page_size - 1) // page_size if total > 0 else 0
        return ReviewListResponse(items=items, total=total, page=page, page_size=page_size, pages=pages)
