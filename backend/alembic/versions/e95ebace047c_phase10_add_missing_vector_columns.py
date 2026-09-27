"""phase10_add_missing_vector_columns

Revision ID: e95ebace047c
Revises: 2521849cc98a
Create Date: 2026-09-27 14:48:41.484613

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e95ebace047c'
down_revision: Union[str, Sequence[str], None] = 'a21fd3e3fb40'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == 'postgresql':
        op.execute("CREATE EXTENSION IF NOT EXISTS vector")
        
        # Add embedding column if it does not exist (idempotent for PostgreSQL)
        op.execute("ALTER TABLE post_embeddings ADD COLUMN IF NOT EXISTS embedding vector(768)")
        op.execute("ALTER TABLE generated_content ADD COLUMN IF NOT EXISTS embedding vector(768)")
    else:
        # SQLite fallback for test environments
        with op.batch_alter_table('post_embeddings', schema=None) as batch_op:
            batch_op.add_column(sa.Column('embedding', sa.JSON(), nullable=True))
        with op.batch_alter_table('generated_content', schema=None) as batch_op:
            batch_op.add_column(sa.Column('embedding', sa.JSON(), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == 'postgresql':
        op.execute("ALTER TABLE post_embeddings DROP COLUMN IF EXISTS embedding")
        op.execute("ALTER TABLE generated_content DROP COLUMN IF EXISTS embedding")
    else:
        with op.batch_alter_table('post_embeddings', schema=None) as batch_op:
            batch_op.drop_column('embedding')
        with op.batch_alter_table('generated_content', schema=None) as batch_op:
            batch_op.drop_column('embedding')
