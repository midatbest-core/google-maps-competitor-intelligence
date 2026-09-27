from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, Text, ForeignKey, JSON, DateTime, UniqueConstraint, Integer
from datetime import datetime, timezone
from .base import Base, TimestampMixin, generate_uuid
from pgvector.sqlalchemy import Vector

class Post(Base, TimestampMixin):
    __tablename__ = "posts"
    __table_args__ = (
        UniqueConstraint("business_id", "source_identifier", name="uq_post_business_source_id"),
        UniqueConstraint("business_id", "source_url", name="uq_post_business_source_url"),
        UniqueConstraint("business_id", "fingerprint", name="uq_post_business_fingerprint"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True, default=generate_uuid)
    business_id: Mapped[str] = mapped_column(ForeignKey("business_profiles.id", ondelete="CASCADE"), nullable=False, index=True)
    source_url: Mapped[str | None] = mapped_column(String(1024))
    source_identifier: Mapped[str | None] = mapped_column(String(255), index=True)
    text_content: Mapped[str | None] = mapped_column(Text)
    published_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    scraped_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    
    # Metadata extracted natively during scraping (not AI)
    cta_link: Mapped[str | None] = mapped_column(String(1024))
    fingerprint: Mapped[str] = mapped_column(String(255), index=True, nullable=False)

    business = relationship("BusinessProfile")
    media = relationship("PostMedia", back_populates="post", cascade="all, delete-orphan")
    ai_analyses = relationship("AIAnalysis", back_populates="post", cascade="all, delete-orphan")
    embeddings = relationship("PostEmbedding", back_populates="post", cascade="all, delete-orphan")


class PostMedia(Base, TimestampMixin):
    __tablename__ = "post_media"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=generate_uuid)
    post_id: Mapped[str] = mapped_column(ForeignKey("posts.id", ondelete="CASCADE"), nullable=False)
    media_url: Mapped[str | None] = mapped_column(String(1024))
    storage_key: Mapped[str | None] = mapped_column(String(1024))
    media_type: Mapped[str | None] = mapped_column(String(50))
    mime_type: Mapped[str | None] = mapped_column(String(255))
    file_size: Mapped[int | None] = mapped_column(Integer)
    width: Mapped[int | None] = mapped_column(Integer)
    height: Mapped[int | None] = mapped_column(Integer)
    checksum: Mapped[str | None] = mapped_column(String(255))
    download_status: Mapped[str] = mapped_column(String(50), default="PENDING")
    error_message: Mapped[str | None] = mapped_column(Text)

    post = relationship("Post", back_populates="media")
