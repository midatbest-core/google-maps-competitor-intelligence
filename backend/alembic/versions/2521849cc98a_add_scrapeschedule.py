"""Add ScrapeSchedule

Revision ID: 2521849cc98a
Revises: d51fd3e3fb43
Create Date: 2026-09-27 14:03:31.618814

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2521849cc98a'
down_revision: Union[str, Sequence[str], None] = 'd51fd3e3fb43'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'scrape_schedules',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('project_id', sa.String(), nullable=False),
        sa.Column('enabled', sa.Boolean(), nullable=False),
        sa.Column('frequency', sa.String(length=50), nullable=False),
        sa.Column('time_of_day', sa.String(length=10), nullable=False),
        sa.Column('timezone', sa.String(length=50), nullable=False),
        sa.Column('next_run_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_run_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('project_id')
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('scrape_schedules')
