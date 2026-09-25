from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, Text, ForeignKey, JSON, DateTime, UniqueConstraint
from datetime import datetime, timezone
from .base import Base, TimestampMixin, generate_uuid
from pgvector.sqlalchemy import Vector

class Post(Base, TimestampMixin):
    __tablename__ = "posts"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=generate_uuid)
    business_id: Mapped[str] = mapped_column(ForeignKey("business_profiles.id", ondelete="CASCADE"), nullable=False, index=True)
    source_url: Mapped[str | None] = mapped_column(String(1024))
    source_identifier: Mapped[str | None] = mapped_column(String(255), index=True)
    text_content: Mapped[str | None] = mapped_column(Text)
    published_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    scraped_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    
    # Metadata extracted natively during scraping (not AI)
    cta_link: Mapped[str | None] = mapped_column(String(1024))
    fingerprint: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)

    # Note: pgvector length depends on embedding model (e.g. 768 for gemini)
    semantic_embedding = mapped_column(Vector(768))

    business = relationship("BusinessProfile")
    media = relationship("PostMedia", back_populates="post", cascade="all, delete-orphan")
    ai_analysis = relationship("AIAnalysis", back_populates="post", uselist=False, cascade="all, delete-orphan")


class PostMedia(Base, TimestampMixin):
    __tablename__ = "post_media"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=generate_uuid)
    post_id: Mapped[str] = mapped_column(ForeignKey("posts.id", ondelete="CASCADE"), nullable=False)
    media_url: Mapped[str | None] = mapped_column(String(1024))
    storage_key: Mapped[str | None] = mapped_column(String(1024))
    media_type: Mapped[str | None] = mapped_column(String(50))
    download_status: Mapped[str] = mapped_column(String(50), default="PENDING")

    post = relationship("Post", back_populates="media")
