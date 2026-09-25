from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, Text, JSON
from .base import Base, TimestampMixin, generate_uuid

class BusinessProfile(Base, TimestampMixin):
    __tablename__ = "business_profiles"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=generate_uuid)
    business_name: Mapped[str] = mapped_column(String(255), nullable=False)
    google_maps_url: Mapped[str | None] = mapped_column(String(1024), unique=True)
    canonical_source_id: Mapped[str | None] = mapped_column(String(255), unique=True, index=True)
    address: Mapped[str | None] = mapped_column(Text)
    category: Mapped[str | None] = mapped_column(String(255))
    metadata_json: Mapped[dict | None] = mapped_column(JSON)
