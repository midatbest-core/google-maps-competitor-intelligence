from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, ForeignKey, Boolean, UniqueConstraint
from .base import Base, TimestampMixin, generate_uuid

class ProjectCompetitor(Base, TimestampMixin):
    __tablename__ = "project_competitors"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=generate_uuid)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    business_id: Mapped[str] = mapped_column(ForeignKey("business_profiles.id", ondelete="CASCADE"), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    __table_args__ = (
        UniqueConstraint("project_id", "business_id", name="uq_project_competitor"),
    )

    project = relationship("Project", back_populates="competitors")
    business = relationship("BusinessProfile")
