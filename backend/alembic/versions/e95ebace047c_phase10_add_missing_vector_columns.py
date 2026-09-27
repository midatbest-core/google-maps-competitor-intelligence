"""phase10_add_missing_vector_columns

Revision ID: e95ebace047c
Revises: 2521849cc98a
Create Date: 2026-09-27 14:48:41.484613

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector


# revision identifiers, used by Alembic.
revision: str = 'e95ebace047c'
down_revision: Union[str, Sequence[str], None] = 'a21fd3e3fb40'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == 'postgresql':
        op.execute("CREATE EXTENSION IF NOT EXISTS vector")
        
        with op.batch_alter_table('post_embeddings', schema=None) as batch_op:
            batch_op.add_column(sa.Column('embedding', Vector(768), nullable=True))
    else:
        # SQLite fallback for test environments
        with op.batch_alter_table('post_embeddings', schema=None) as batch_op:
            batch_op.add_column(sa.Column('embedding', sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('post_embeddings', schema=None) as batch_op:
        batch_op.drop_column('embedding')
