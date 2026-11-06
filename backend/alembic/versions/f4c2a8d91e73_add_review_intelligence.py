"""Add review intelligence.

Revision ID: f4c2a8d91e73
Revises: 2521849cc98a
Create Date: 2026-11-05 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f4c2a8d91e73"
down_revision: Union[str, Sequence[str], None] = "2521849cc98a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "review_intelligence",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("project_id", sa.String(), nullable=False),
        sa.Column("business_id", sa.String(), nullable=False),
        sa.Column("reviews_analyzed_count", sa.Integer(), nullable=False),
        sa.Column("overall_sentiment", sa.String(length=255), nullable=True),
        sa.Column("positive_percentage", sa.Float(), nullable=True),
        sa.Column("neutral_percentage", sa.Float(), nullable=True),
        sa.Column("negative_percentage", sa.Float(), nullable=True),
        sa.Column("average_rating", sa.Float(), nullable=True),
        sa.Column("praise_themes", sa.JSON(), nullable=True),
        sa.Column("complaint_themes", sa.JSON(), nullable=True),
        sa.Column("pain_points", sa.JSON(), nullable=True),
        sa.Column("customer_needs", sa.JSON(), nullable=True),
        sa.Column("frequently_mentioned_services", sa.JSON(), nullable=True),
        sa.Column("strengths", sa.JSON(), nullable=True),
        sa.Column("weaknesses", sa.JSON(), nullable=True),
        sa.Column("business_opportunities", sa.JSON(), nullable=True),
        sa.Column("recommended_actions", sa.JSON(), nullable=True),
        sa.Column("analysis_provider", sa.String(length=50), nullable=True),
        sa.Column("model_version", sa.String(length=50), nullable=True),
        sa.Column("analyzed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["business_id"], ["business_profiles.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_review_intelligence_business_id"),
        "review_intelligence",
        ["business_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_review_intelligence_project_id"),
        "review_intelligence",
        ["project_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_review_intelligence_project_id"),
        table_name="review_intelligence",
    )
    op.drop_index(
        op.f("ix_review_intelligence_business_id"),
        table_name="review_intelligence",
    )
    op.drop_table("review_intelligence")
