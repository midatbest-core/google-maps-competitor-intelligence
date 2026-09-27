"""phase6_1_content_hardening

Revision ID: c41fd3e3fb42
Revises: b31fd3e3fb41
Create Date: 2026-09-27 01:40:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

revision: str = 'c41fd3e3fb42'
down_revision: Union[str, Sequence[str], None] = 'b31fd3e3fb41'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    # Use Vector type from pgvector
    with op.batch_alter_table('generated_content', schema=None) as batch_op:
        if bind.dialect.name == 'postgresql':
            batch_op.add_column(sa.Column('embedding', Vector(768), nullable=True))
        else:
            batch_op.add_column(sa.Column('embedding', sa.JSON(), nullable=True))

def downgrade() -> None:
    with op.batch_alter_table('generated_content', schema=None) as batch_op:
        batch_op.drop_column('embedding')
