from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, ForeignKey, Integer, Float, JSON, DateTime
from datetime import datetime, timezone
from .base import Base, TimestampMixin, generate_uuid

class ReviewIntelligence(Base, TimestampMixin):
    __tablename__ = "review_intelligence"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=generate_uuid)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    business_id: Mapped[str] = mapped_column(ForeignKey("business_profiles.id", ondelete="CASCADE"), nullable=False, index=True)
    
    reviews_analyzed_count: Mapped[int] = mapped_column(Integer, default=0)
    overall_sentiment: Mapped[str | None] = mapped_column(String(255))
    positive_percentage: Mapped[float | None] = mapped_column(Float)
    neutral_percentage: Mapped[float | None] = mapped_column(Float)
    negative_percentage: Mapped[float | None] = mapped_column(Float)
    average_rating: Mapped[float | None] = mapped_column(Float)
    
    praise_themes: Mapped[list[str] | None] = mapped_column(JSON)
    complaint_themes: Mapped[list[str] | None] = mapped_column(JSON)
    pain_points: Mapped[list[str] | None] = mapped_column(JSON)
    customer_needs: Mapped[list[str] | None] = mapped_column(JSON)
    frequently_mentioned_services: Mapped[list[str] | None] = mapped_column(JSON)
    strengths: Mapped[list[str] | None] = mapped_column(JSON)
    weaknesses: Mapped[list[str] | None] = mapped_column(JSON)
    business_opportunities: Mapped[list[str] | None] = mapped_column(JSON)
    recommended_actions: Mapped[list[str] | None] = mapped_column(JSON)
    
    analysis_provider: Mapped[str | None] = mapped_column(String(50))
    model_version: Mapped[str | None] = mapped_column(String(50))
    analyzed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    project = relationship("Project")
    business = relationship("BusinessProfile")
