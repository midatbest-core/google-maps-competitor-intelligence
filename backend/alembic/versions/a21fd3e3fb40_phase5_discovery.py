"""phase5_discovery

Revision ID: a21fd3e3fb40
Revises: a6de632107ba
Create Date: 2026-09-27 01:00:36.314944

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a21fd3e3fb40'
down_revision: Union[str, Sequence[str], None] = 'a6de632107ba'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('discovery_runs',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('project_id', sa.String(), nullable=False),
        sa.Column('query', sa.String(length=500), nullable=True),
        sa.Column('location', sa.String(length=500), nullable=True),
        sa.Column('latitude', sa.Float(), nullable=True),
        sa.Column('longitude', sa.Float(), nullable=True),
        sa.Column('radius', sa.Integer(), nullable=True),
        sa.Column('category', sa.String(length=255), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=False, server_default='QUEUED'),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('total_candidates', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('duplicates_skipped', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('discovery_runs', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_discovery_runs_project_id'), ['project_id'], unique=False)

    op.create_table('discovery_candidates',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('discovery_run_id', sa.String(), nullable=False),
        sa.Column('source_identifier', sa.String(length=255), nullable=True),
        sa.Column('source_url', sa.String(length=1024), nullable=True),
        sa.Column('business_name', sa.String(length=255), nullable=False),
        sa.Column('category', sa.String(length=255), nullable=True),
        sa.Column('address', sa.Text(), nullable=True),
        sa.Column('locality', sa.String(length=255), nullable=True),
        sa.Column('latitude', sa.Float(), nullable=True),
        sa.Column('longitude', sa.Float(), nullable=True),
        sa.Column('rating', sa.Float(), nullable=True),
        sa.Column('review_count', sa.Integer(), nullable=True),
        sa.Column('phone', sa.String(length=50), nullable=True),
        sa.Column('website', sa.String(length=1024), nullable=True),
        sa.Column('normalized_name', sa.String(length=255), nullable=True),
        sa.Column('normalized_address', sa.Text(), nullable=True),
        sa.Column('discovery_query', sa.String(length=500), nullable=True),
        sa.Column('discovered_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False, server_default='NEW'),
        sa.Column('relevance_score', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['discovery_run_id'], ['discovery_runs.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('discovery_run_id', 'source_identifier', name='uq_discovery_candidate_source_id')
    )
    with op.batch_alter_table('discovery_candidates', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_discovery_candidates_discovery_run_id'), ['discovery_run_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_discovery_candidates_source_identifier'), ['source_identifier'], unique=False)

def downgrade() -> None:
    with op.batch_alter_table('discovery_candidates', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_discovery_candidates_source_identifier'))
        batch_op.drop_index(batch_op.f('ix_discovery_candidates_discovery_run_id'))
    op.drop_table('discovery_candidates')
    
    with op.batch_alter_table('discovery_runs', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_discovery_runs_project_id'))
    op.drop_table('discovery_runs')
