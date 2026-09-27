"""phase3_ingestion_and_media

Revision ID: 3e45af5d604c
Revises: 
Create Date: 2026-09-27 00:34:04.028204

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3e45af5d604c'
down_revision: Union[str, Sequence[str], None] = '000000000000'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Post table
    with op.batch_alter_table('posts', schema=None) as batch_op:
        # Drop the unique constraint on fingerprint. Note: name depends on DB, often it's an index.
        batch_op.drop_index('ix_posts_fingerprint')
        batch_op.create_index('ix_posts_fingerprint', ['fingerprint'], unique=False)
        
        batch_op.create_unique_constraint('uq_post_business_source_id', ['business_id', 'source_identifier'])
        batch_op.create_unique_constraint('uq_post_business_source_url', ['business_id', 'source_url'])
        batch_op.create_unique_constraint('uq_post_business_fingerprint', ['business_id', 'fingerprint'])

    # PostMedia table
    with op.batch_alter_table('post_media', schema=None) as batch_op:
        batch_op.add_column(sa.Column('mime_type', sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column('file_size', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('width', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('height', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('checksum', sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column('error_message', sa.Text(), nullable=True))

    # ScrapeObservation table
    with op.batch_alter_table('scrape_observations', schema=None) as batch_op:
        batch_op.create_unique_constraint('uq_scrape_obs_run_post', ['scrape_run_competitor_id', 'post_id'])

def downgrade() -> None:
    with op.batch_alter_table('scrape_observations', schema=None) as batch_op:
        batch_op.drop_constraint('uq_scrape_obs_run_post', type_='unique')

    with op.batch_alter_table('post_media', schema=None) as batch_op:
        batch_op.drop_column('error_message')
        batch_op.drop_column('checksum')
        batch_op.drop_column('height')
        batch_op.drop_column('width')
        batch_op.drop_column('file_size')
        batch_op.drop_column('mime_type')

    with op.batch_alter_table('posts', schema=None) as batch_op:
        batch_op.drop_constraint('uq_post_business_fingerprint', type_='unique')
        batch_op.drop_constraint('uq_post_business_source_url', type_='unique')
        batch_op.drop_constraint('uq_post_business_source_id', type_='unique')
        batch_op.drop_index('ix_posts_fingerprint')
        batch_op.create_index('ix_posts_fingerprint', ['fingerprint'], unique=True)
