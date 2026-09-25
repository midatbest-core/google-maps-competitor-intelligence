from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, ForeignKey, Integer, DateTime, Text, JSON
from datetime import datetime
from .base import Base, TimestampMixin, generate_uuid

class ScrapeRun(Base, TimestampMixin):
    __tablename__ = "scrape_runs"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=generate_uuid)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    start_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    end_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(50), default="QUEUED") # QUEUED, RUNNING, PARTIAL_SUCCESS, SUCCESS, FAILED
    
    # Aggregated Counters
    competitors_attempted: Mapped[int] = mapped_column(Integer, default=0)
    competitors_succeeded: Mapped[int] = mapped_column(Integer, default=0)
    competitors_failed: Mapped[int] = mapped_column(Integer, default=0)
    
    error_logs: Mapped[list | None] = mapped_column(JSON)

    project = relationship("Project", back_populates="scrape_runs")
    competitor_runs = relationship("ScrapeRunCompetitor", back_populates="scrape_run", cascade="all, delete-orphan")


class ScrapeRunCompetitor(Base, TimestampMixin):
    __tablename__ = "scrape_run_competitors"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=generate_uuid)
    scrape_run_id: Mapped[str] = mapped_column(ForeignKey("scrape_runs.id", ondelete="CASCADE"), nullable=False)
    business_id: Mapped[str] = mapped_column(ForeignKey("business_profiles.id", ondelete="CASCADE"), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="PENDING") # PENDING, RUNNING, SUCCESS, NO_DATA, VERIFICATION_REQUIRED, ERROR
    
    posts_discovered: Mapped[int] = mapped_column(Integer, default=0)
    new_posts: Mapped[int] = mapped_column(Integer, default=0)
    duplicates_skipped: Mapped[int] = mapped_column(Integer, default=0)
    
    error_message: Mapped[str | None] = mapped_column(Text)
    
    scrape_run = relationship("ScrapeRun", back_populates="competitor_runs")
    business = relationship("BusinessProfile")
    observations = relationship("ScrapeObservation", back_populates="scrape_run_competitor", cascade="all, delete-orphan")

class ScrapeObservation(Base, TimestampMixin):
    __tablename__ = "scrape_observations"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=generate_uuid)
    scrape_run_competitor_id: Mapped[str] = mapped_column(ForeignKey("scrape_run_competitors.id", ondelete="CASCADE"), nullable=False, index=True)
    post_id: Mapped[str] = mapped_column(ForeignKey("posts.id", ondelete="CASCADE"), nullable=False, index=True)
    is_new: Mapped[bool] = mapped_column(default=False)

    scrape_run_competitor = relationship("ScrapeRunCompetitor", back_populates="observations")
    # post = relationship("Post") # Optional depending on access patterns

