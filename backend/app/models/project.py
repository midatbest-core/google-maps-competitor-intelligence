from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, Text, ForeignKey, JSON
from .base import Base, TimestampMixin, generate_uuid
from typing import List

class Project(Base, TimestampMixin):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=generate_uuid)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    own_business_id: Mapped[str | None] = mapped_column(ForeignKey("business_profiles.id"))
    maps_url: Mapped[str | None] = mapped_column(String(1024))
    keywords: Mapped[list[str] | None] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(50), default="ACTIVE")

    # relationships
    own_business = relationship("BusinessProfile", foreign_keys=[own_business_id])
    competitors = relationship("ProjectCompetitor", back_populates="project", cascade="all, delete-orphan")
    scrape_runs = relationship("ScrapeRun", back_populates="project", cascade="all, delete-orphan")
