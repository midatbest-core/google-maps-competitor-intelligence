"""Add reviews and intelligence reports.

Revision ID: c1a2b3d4e5f6
Revises: b8a91d6f3c42
Create Date: 2026-11-07 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c1a2b3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "b8a91d6f3c42"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create reviews table
    op.create_table(
        "reviews",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("business_id", sa.String(), nullable=False),
        sa.Column("source", sa.String(length=50), nullable=False, server_default="browser_scraper"),
        sa.Column("source_id", sa.String(length=255), nullable=True),
        sa.Column("author_name", sa.String(length=255), nullable=True),
        sa.Column("author_photo_url", sa.Text(), nullable=True),
        sa.Column("rating", sa.Float(), nullable=True),
        sa.Column("text", sa.Text(), nullable=True),
        sa.Column("language", sa.String(length=20), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("relative_time_description", sa.String(length=100), nullable=True),
        sa.Column("response_text", sa.Text(), nullable=True),
        sa.Column("response_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sentiment", sa.String(length=50), nullable=True),
        sa.Column("aspects", sa.JSON(), nullable=True),
        sa.Column("fingerprint", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["business_id"], ["business_profiles.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_reviews_business_id"), "reviews", ["business_id"], unique=False)
    op.create_index(op.f("ix_reviews_source_id"), "reviews", ["source_id"], unique=False)
    op.create_index(op.f("ix_reviews_fingerprint"), "reviews", ["fingerprint"], unique=False)

    # 2. Create intelligence_reports table
    op.create_table(
        "intelligence_reports",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("project_id", sa.String(), nullable=False),
        sa.Column("posts_analyzed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("reviews_analyzed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("competitors_analyzed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("competitor_insights", sa.JSON(), nullable=True),
        sa.Column("marketing_intelligence", sa.JSON(), nullable=True),
        sa.Column("strategic_disconnects", sa.JSON(), nullable=True),
        sa.Column("business_opportunities", sa.JSON(), nullable=True),
        sa.Column("actionable_recommendations", sa.JSON(), nullable=True),
        sa.Column("content_ideas", sa.JSON(), nullable=True),
        sa.Column("provider", sa.String(length=50), nullable=True),
        sa.Column("model_name", sa.String(length=100), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="COMPLETED"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_intelligence_reports_project_id"), "intelligence_reports", ["project_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_intelligence_reports_project_id"), table_name="intelligence_reports")
    op.drop_table("intelligence_reports")
    op.drop_index(op.f("ix_reviews_fingerprint"), table_name="reviews")
    op.drop_index(op.f("ix_reviews_source_id"), table_name="reviews")
    op.drop_index(op.f("ix_reviews_business_id"), table_name="reviews")
    op.drop_table("reviews")

