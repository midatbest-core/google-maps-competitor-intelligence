"""phase4_intelligence

Revision ID: a6de632107ba
Revises: 3e45af5d604c
Create Date: 2026-09-27 00:44:59.609826

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a6de632107ba'
down_revision: Union[str, Sequence[str], None] = '3e45af5d604c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Post model: Drop semantic_embedding
    with op.batch_alter_table('posts', schema=None) as batch_op:
        batch_op.drop_column('semantic_embedding')

    # AIAnalysis model: Drop unique constraint on post_id, add new columns
    with op.batch_alter_table('ai_analyses', schema=None) as batch_op:
        try:
            batch_op.drop_constraint('ai_analyses_post_id_key', type_='unique')
        except Exception:
            pass
        try:
            batch_op.drop_index('ix_ai_analyses_post_id')
        except Exception:
            pass
        
        batch_op.add_column(sa.Column('analysis_version', sa.String(length=50), server_default="v1", nullable=False))
        batch_op.add_column(sa.Column('offer_or_promotion', sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column('sentiment', sa.String(length=50), nullable=True))
        batch_op.add_column(sa.Column('summary', sa.Text(), nullable=True))
        
        batch_op.drop_column('offer_info')
        batch_op.create_unique_constraint('uq_ai_analysis_identity', ['post_id', 'provider', 'model_name', 'analysis_version'])

    # PostEmbedding model
    op.create_table('post_embeddings',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('post_id', sa.String(), nullable=False),
        sa.Column('embedding_model', sa.String(length=100), nullable=False),
        sa.Column('embedding_version', sa.String(length=50), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['post_id'], ['posts.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('post_id', 'embedding_model', 'embedding_version', name='uq_post_embedding_identity')
    )
    with op.batch_alter_table('post_embeddings', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_post_embeddings_post_id'), ['post_id'], unique=False)
    

def downgrade() -> None:
    op.drop_table('post_embeddings')
    
    with op.batch_alter_table('ai_analyses', schema=None) as batch_op:
        batch_op.drop_constraint('uq_ai_analysis_identity', type_='unique')
        batch_op.add_column(sa.Column('offer_info', sa.String(length=255), nullable=True))
        batch_op.drop_column('summary')
        batch_op.drop_column('sentiment')
        batch_op.drop_column('offer_or_promotion')
        batch_op.drop_column('analysis_version')
        batch_op.create_unique_constraint('ai_analyses_post_id_key', ['post_id'])
