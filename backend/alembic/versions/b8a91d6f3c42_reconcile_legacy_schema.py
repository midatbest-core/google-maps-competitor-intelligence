"""Reconcile legacy timestamp nullability and analysis index.

Revision ID: b8a91d6f3c42
Revises: f4c2a8d91e73
Create Date: 2026-11-05 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b8a91d6f3c42"
down_revision: Union[str, Sequence[str], None] = "f4c2a8d91e73"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


LEGACY_TIMESTAMP_TABLES = (
    "ai_analyses",
    "business_profiles",
    "discovery_candidates",
    "discovery_runs",
    "generated_content",
    "post_embeddings",
    "post_media",
    "posts",
    "project_competitors",
    "projects",
    "scrape_observations",
    "scrape_run_competitors",
    "scrape_runs",
)


def _assert_no_null_timestamps() -> None:
    connection = op.get_bind()
    tables_with_nulls = []

    for table_name in LEGACY_TIMESTAMP_TABLES:
        table = sa.table(
            table_name,
            sa.column("created_at"),
            sa.column("updated_at"),
        )
        null_count = connection.execute(
            sa.select(sa.func.count())
            .select_from(table)
            .where(sa.or_(table.c.created_at.is_(None), table.c.updated_at.is_(None)))
        ).scalar_one()
        if null_count:
            tables_with_nulls.append(f"{table_name} ({null_count} rows)")

    if tables_with_nulls:
        details = ", ".join(tables_with_nulls)
        raise RuntimeError(
            "Cannot enforce non-null legacy timestamps. Resolve NULL created_at/updated_at "
            f"values before rerunning this migration: {details}"
        )


def _set_timestamp_nullability(*, nullable: bool) -> None:
    for table_name in LEGACY_TIMESTAMP_TABLES:
        with op.batch_alter_table(table_name) as batch_op:
            batch_op.alter_column(
                "created_at",
                existing_type=sa.DateTime(timezone=True),
                nullable=nullable,
            )
            batch_op.alter_column(
                "updated_at",
                existing_type=sa.DateTime(timezone=True),
                nullable=nullable,
            )


def upgrade() -> None:
    _assert_no_null_timestamps()
    _set_timestamp_nullability(nullable=False)
    op.create_index(
        op.f("ix_ai_analyses_post_id"),
        "ai_analyses",
        ["post_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_ai_analyses_post_id"), table_name="ai_analyses")
    _set_timestamp_nullability(nullable=True)
