"""phase6_content

Revision ID: b31fd3e3fb41
Revises: a21fd3e3fb40
Create Date: 2026-09-27 01:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b31fd3e3fb41'
down_revision: Union[str, Sequence[str], None] = 'a21fd3e3fb40'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('generated_content', schema=None) as batch_op:
        try:
            batch_op.drop_index('ix_generated_content_fingerprint')
        except Exception:
            pass
        try:
            batch_op.drop_constraint('generated_content_fingerprint_key', type_='unique')
        except Exception:
            pass

        batch_op.add_column(sa.Column('generation_type', sa.String(length=50), server_default="IDEA", nullable=False))
        batch_op.add_column(sa.Column('content_type', sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column('prompt_version', sa.String(length=50), nullable=True))
        batch_op.add_column(sa.Column('source_context', sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column('error_message', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('parent_generation_id', sa.String(), nullable=True))
        batch_op.add_column(sa.Column('regeneration_reason', sa.Text(), nullable=True))
        
        batch_op.alter_column('provider', existing_type=sa.String(length=50), nullable=True)
        batch_op.alter_column('model_name', existing_type=sa.String(length=100), nullable=True)
        batch_op.alter_column('generated_idea', existing_type=sa.Text(), nullable=True)
        batch_op.alter_column('topic', existing_type=sa.String(length=255), nullable=True)

        batch_op.create_foreign_key('fk_parent_generation_id', 'generated_content', ['parent_generation_id'], ['id'], ondelete='SET NULL')
        
        batch_op.create_index(batch_op.f('ix_generated_content_fingerprint'), ['fingerprint'], unique=False)
        batch_op.create_index(batch_op.f('ix_generated_content_project_id'), ['project_id'], unique=False)

def downgrade() -> None:
    pass
