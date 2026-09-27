from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, ForeignKey, JSON, Float, Text, DateTime, UniqueConstraint
from datetime import datetime, timezone
from .base import Base, TimestampMixin, generate_uuid

class AIAnalysis(Base, TimestampMixin):
    __tablename__ = "ai_analyses"
    __table_args__ = (
        UniqueConstraint("post_id", "provider", "model_name", "analysis_version", name="uq_ai_analysis_identity"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True, default=generate_uuid)
    post_id: Mapped[str] = mapped_column(ForeignKey("posts.id", ondelete="CASCADE"), nullable=False, index=True)
    provider: Mapped[str] = mapped_column(String(50))
    model_name: Mapped[str] = mapped_column(String(100))
    analysis_version: Mapped[str] = mapped_column(String(50), default="v1")

    topic: Mapped[str | None] = mapped_column(String(255))
    subtopic: Mapped[str | None] = mapped_column(String(255))
    keywords: Mapped[list[str] | None] = mapped_column(JSON)
    content_type: Mapped[str | None] = mapped_column(String(100))
    cta_type: Mapped[str | None] = mapped_column(String(100))
    offer_or_promotion: Mapped[str | None] = mapped_column(String(255))
    sentiment: Mapped[str | None] = mapped_column(String(50))
    summary: Mapped[str | None] = mapped_column(Text)

    confidence: Mapped[float | None] = mapped_column(Float)
    raw_analysis: Mapped[dict | None] = mapped_column(JSON)
    analyzed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    post = relationship("Post", back_populates="ai_analyses")

from pgvector.sqlalchemy import Vector
from app.core.config import settings

class PostEmbedding(Base, TimestampMixin):
    __tablename__ = "post_embeddings"
    __table_args__ = (
        UniqueConstraint("post_id", "embedding_model", "embedding_version", name="uq_post_embedding_identity"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True, default=generate_uuid)
    post_id: Mapped[str] = mapped_column(ForeignKey("posts.id", ondelete="CASCADE"), nullable=False, index=True)
    embedding_model: Mapped[str] = mapped_column(String(100))
    embedding_version: Mapped[str] = mapped_column(String(50))

    # 768 is a fallback; configurable if possible, but pgvector requires fixed dimension at class level in SQLAlchemy ORM.
    # We will use 768 for this phase as it matches Gemini's default.
    embedding = mapped_column(Vector(768))

    post = relationship("Post", back_populates="embeddings")


class GeneratedContent(Base, TimestampMixin):
    __tablename__ = "generated_content"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=generate_uuid)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)

    generation_type: Mapped[str] = mapped_column(String(50), default="IDEA") # IDEA or FULL
    topic: Mapped[str | None] = mapped_column(String(255))
    generated_idea: Mapped[str | None] = mapped_column(Text)
    full_copy: Mapped[str | None] = mapped_column(Text)
    keywords: Mapped[list[str] | None] = mapped_column(JSON)
    cta: Mapped[str | None] = mapped_column(String(255))
    image_concept: Mapped[str | None] = mapped_column(Text)
    content_type: Mapped[str | None] = mapped_column(String(100))

    provider: Mapped[str | None] = mapped_column(String(50))
    model_name: Mapped[str | None] = mapped_column(String(100))
    prompt_version: Mapped[str | None] = mapped_column(String(50))

    source_context: Mapped[dict | None] = mapped_column(JSON)
    fingerprint: Mapped[str | None] = mapped_column(String(255), index=True)
    status: Mapped[str] = mapped_column(String(50), default="QUEUED") # QUEUED, RUNNING, SUCCESS, FAILED, REJECTED_DUPLICATE
    error_message: Mapped[str | None] = mapped_column(Text)

    parent_generation_id: Mapped[str | None] = mapped_column(ForeignKey("generated_content.id", ondelete="SET NULL"), nullable=True)
    regeneration_reason: Mapped[str | None] = mapped_column(Text)

    embedding = mapped_column(Vector(768))

    project = relationship("Project")
