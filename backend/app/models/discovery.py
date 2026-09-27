from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, ForeignKey, Integer, Float, DateTime, Text, UniqueConstraint
from datetime import datetime, timezone
from .base import Base, TimestampMixin, generate_uuid

class DiscoveryRun(Base, TimestampMixin):
    __tablename__ = "discovery_runs"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=generate_uuid)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    query: Mapped[str | None] = mapped_column(String(500))
    location: Mapped[str | None] = mapped_column(String(500))
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)
    radius: Mapped[int | None] = mapped_column(Integer)
    category: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(50), default="QUEUED")
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    total_candidates: Mapped[int] = mapped_column(Integer, default=0)
    duplicates_skipped: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str | None] = mapped_column(Text)

    project = relationship("Project", back_populates="discovery_runs")
    candidates = relationship("DiscoveryCandidate", back_populates="run", cascade="all, delete-orphan")


class DiscoveryCandidate(Base, TimestampMixin):
    __tablename__ = "discovery_candidates"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=generate_uuid)
    discovery_run_id: Mapped[str] = mapped_column(ForeignKey("discovery_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    source_identifier: Mapped[str | None] = mapped_column(String(255), index=True)
    source_url: Mapped[str | None] = mapped_column(String(1024))
    business_name: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str | None] = mapped_column(String(255))
    address: Mapped[str | None] = mapped_column(Text)
    locality: Mapped[str | None] = mapped_column(String(255))
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)
    rating: Mapped[float | None] = mapped_column(Float)
    review_count: Mapped[int | None] = mapped_column(Integer)
    phone: Mapped[str | None] = mapped_column(String(50))
    website: Mapped[str | None] = mapped_column(String(1024))
    normalized_name: Mapped[str | None] = mapped_column(String(255))
    normalized_address: Mapped[str | None] = mapped_column(Text)
    discovery_query: Mapped[str | None] = mapped_column(String(500))
    discovered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    status: Mapped[str] = mapped_column(String(50), default="NEW") # NEW, SELECTED, REJECTED, ALREADY_COMPETITOR
    relevance_score: Mapped[float | None] = mapped_column(Float)

    run = relationship("DiscoveryRun", back_populates="candidates")

    __table_args__ = (
        UniqueConstraint("discovery_run_id", "source_identifier", name="uq_discovery_candidate_source_id"),
    )
