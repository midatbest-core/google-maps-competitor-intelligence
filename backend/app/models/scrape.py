from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, ForeignKey, Integer, DateTime, Text, JSON, UniqueConstraint, Boolean
from datetime import datetime
from .base import Base, TimestampMixin, generate_uuid

class ScrapeSchedule(Base, TimestampMixin):
    __tablename__ = "scrape_schedules"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=generate_uuid)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, unique=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    frequency: Mapped[str] = mapped_column(String(50), default="DAILY")
    time_of_day: Mapped[str] = mapped_column(String(10), nullable=False)
    timezone: Mapped[str] = mapped_column(String(50), nullable=False)
    next_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    project = relationship("Project", back_populates="scrape_schedule")

class ScrapeRun(Base, TimestampMixin):
    __tablename__ = "scrape_runs"
    __table_args__ = (UniqueConstraint("project_id", "run_number", name="uq_scrape_runs_project_run_number"),)

    id: Mapped[str] = mapped_column(String, primary_key=True, default=generate_uuid)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    run_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    start_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    end_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(50), default="QUEUED") # QUEUED, RUNNING, PARTIAL_SUCCESS, SUCCESS, FAILED
    
    # Aggregated Counters
    competitors_attempted: Mapped[int] = mapped_column(Integer, default=0)
    competitors_succeeded: Mapped[int] = mapped_column(Integer, default=0)
    competitors_failed: Mapped[int] = mapped_column(Integer, default=0)
    
    error_logs: Mapped[list | None] = mapped_column(JSON)

    project = relationship("Project", back_populates="scrape_runs")
    competitor_runs = relationship(
        "ScrapeRunCompetitor",
        back_populates="scrape_run",
        cascade="all, delete-orphan",
        order_by="ScrapeRunCompetitor.created_at.asc(), ScrapeRunCompetitor.id.asc()"
    )

    @property
    def display_name(self) -> str:
        if self.run_number is not None:
            return f"Scrape {self.run_number:03d}"
        return f"Scrape #{self.id[:8]}"

    @property
    def total_competitors(self) -> int:
        if self.competitor_runs:
            return len(self.competitor_runs)
        return self.competitors_attempted or 0

    @property
    def competitors_completed(self) -> int:
        if not self.competitor_runs:
            return (self.competitors_succeeded or 0) + (self.competitors_failed or 0)
        return sum(1 for c in self.competitor_runs if c.status in ("SUCCESS", "NO_DATA", "FAILED", "ERROR"))

    @property
    def competitors_remaining(self) -> int:
        return max(0, self.total_competitors - self.competitors_completed)

    @property
    def currently_processing_index(self) -> int | None:
        if not self.competitor_runs:
            return None
        for idx, c in enumerate(self.competitor_runs, 1):
            if c.status == "RUNNING":
                return idx
        return None

    @property
    def currently_processing_name(self) -> str | None:
        if not self.competitor_runs:
            return None
        for c in self.competitor_runs:
            if c.status == "RUNNING":
                return c.business.business_name if (c.business and c.business.business_name) else "Competitor"
        return None

    @property
    def estimated_remaining_seconds(self) -> int | None:
        if self.status in ("SUCCESS", "FAILED", "CANCELLED", "PARTIAL_SUCCESS", "PAUSED_MANUAL_INTERVENTION"):
            return 0
        rem = self.competitors_remaining
        # Formula: Remaining competitors * 60 seconds (1 minute per competitor)
        return rem * 60

    @property
    def estimated_remaining_formatted(self) -> str:
        if self.status == "SUCCESS":
            return "Completed"
        if self.status in ("FAILED", "CANCELLED", "PARTIAL_SUCCESS", "PAUSED_MANUAL_INTERVENTION"):
            return self.status
        rem = self.competitors_remaining
        if rem <= 0:
            return "Completing..."
        rem_seconds = rem * 60
        if rem_seconds < 60:
            return f"{rem_seconds}s remaining"
        elif rem_seconds == 60:
            return "~1 minute remaining"
        else:
            minutes = rem
            return f"~{minutes} minutes remaining"


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
    __table_args__ = (
        UniqueConstraint("scrape_run_competitor_id", "post_id", name="uq_scrape_obs_run_post"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True, default=generate_uuid)
    scrape_run_competitor_id: Mapped[str] = mapped_column(ForeignKey("scrape_run_competitors.id", ondelete="CASCADE"), nullable=False, index=True)
    post_id: Mapped[str] = mapped_column(ForeignKey("posts.id", ondelete="CASCADE"), nullable=False, index=True)
    is_new: Mapped[bool] = mapped_column(default=False)

    scrape_run_competitor = relationship("ScrapeRunCompetitor", back_populates="observations")
    # post = relationship("Post") # Optional depending on access patterns

