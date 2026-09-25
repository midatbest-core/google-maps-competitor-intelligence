from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, ForeignKey, JSON, Float, Text, DateTime
from datetime import datetime, timezone
from .base import Base, TimestampMixin, generate_uuid

class AIAnalysis(Base, TimestampMixin):
    __tablename__ = "ai_analyses"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=generate_uuid)
    post_id: Mapped[str] = mapped_column(ForeignKey("posts.id", ondelete="CASCADE"), nullable=False, unique=True)
    provider: Mapped[str] = mapped_column(String(50))
    model_name: Mapped[str] = mapped_column(String(100))
    
    topic: Mapped[str | None] = mapped_column(String(255))
    subtopic: Mapped[str | None] = mapped_column(String(255))
    keywords: Mapped[list[str] | None] = mapped_column(JSON)
    content_type: Mapped[str | None] = mapped_column(String(100))
    cta_type: Mapped[str | None] = mapped_column(String(100))
    offer_info: Mapped[str | None] = mapped_column(String(255))
    
    confidence: Mapped[float | None] = mapped_column(Float)
    raw_analysis: Mapped[dict | None] = mapped_column(JSON)
    analyzed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    post = relationship("Post", back_populates="ai_analysis")


class GeneratedContent(Base, TimestampMixin):
    __tablename__ = "generated_content"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=generate_uuid)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    
    topic: Mapped[str] = mapped_column(String(255))
    generated_idea: Mapped[str] = mapped_column(Text)
    full_copy: Mapped[str | None] = mapped_column(Text)
    keywords: Mapped[list[str] | None] = mapped_column(JSON)
    cta: Mapped[str | None] = mapped_column(String(255))
    image_concept: Mapped[str | None] = mapped_column(Text)
    
    provider: Mapped[str] = mapped_column(String(50))
    model_name: Mapped[str] = mapped_column(String(100))
    fingerprint: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    status: Mapped[str] = mapped_column(String(50), default="DRAFT") # DRAFT, APPROVED, REJECTED

    project = relationship("Project")
