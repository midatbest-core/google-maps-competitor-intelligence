"""baseline

Revision ID: 000000000000
Revises: 
Create Date: 2026-09-27 00:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '000000000000'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    # 1. business_profiles
    op.create_table('business_profiles',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('business_name', sa.String(length=255), nullable=False),
        sa.Column('google_maps_url', sa.String(length=1024), nullable=True),
        sa.Column('canonical_source_id', sa.String(length=255), nullable=True),
        sa.Column('address', sa.Text(), nullable=True),
        sa.Column('category', sa.String(length=255), nullable=True),
        sa.Column('metadata_json', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('google_maps_url')
    )
    op.create_index(op.f('ix_business_profiles_canonical_source_id'), 'business_profiles', ['canonical_source_id'], unique=True)

    # 2. projects
    op.create_table('projects',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('own_business_id', sa.String(), nullable=True),
        sa.Column('maps_url', sa.String(length=1024), nullable=True),
        sa.Column('keywords', sa.JSON(), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=False, server_default="ACTIVE"),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['own_business_id'], ['business_profiles.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

    # 3. project_competitors
    op.create_table('project_competitors',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('project_id', sa.String(), nullable=False),
        sa.Column('business_id', sa.String(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default="1"),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['business_id'], ['business_profiles.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('project_id', 'business_id', name='uq_project_competitor')
    )

    # 4. posts
    op.create_table('posts',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('business_id', sa.String(), nullable=False),
        sa.Column('source_url', sa.String(length=1024), nullable=True),
        sa.Column('source_identifier', sa.String(length=255), nullable=True),
        sa.Column('text_content', sa.Text(), nullable=True),
        sa.Column('published_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('scraped_date', sa.DateTime(timezone=True), nullable=False),
        sa.Column('cta_link', sa.String(length=1024), nullable=True),
        sa.Column('fingerprint', sa.String(length=255), nullable=False),
        sa.Column('semantic_embedding', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['business_id'], ['business_profiles.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_posts_business_id'), 'posts', ['business_id'], unique=False)
    op.create_index(op.f('ix_posts_source_identifier'), 'posts', ['source_identifier'], unique=False)
    op.create_index(op.f('ix_posts_fingerprint'), 'posts', ['fingerprint'], unique=True)

    # 5. post_media
    op.create_table('post_media',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('post_id', sa.String(), nullable=False),
        sa.Column('media_url', sa.String(length=1024), nullable=True),
        sa.Column('storage_key', sa.String(length=1024), nullable=True),
        sa.Column('media_type', sa.String(length=50), nullable=True),
        sa.Column('download_status', sa.String(length=50), nullable=False, server_default="PENDING"),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['post_id'], ['posts.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )

    # 6. scrape_runs
    op.create_table('scrape_runs',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('project_id', sa.String(), nullable=False),
        sa.Column('start_time', sa.DateTime(timezone=True), nullable=True),
        sa.Column('end_time', sa.DateTime(timezone=True), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=False, server_default="QUEUED"),
        sa.Column('competitors_attempted', sa.Integer(), nullable=False, server_default="0"),
        sa.Column('competitors_succeeded', sa.Integer(), nullable=False, server_default="0"),
        sa.Column('competitors_failed', sa.Integer(), nullable=False, server_default="0"),
        sa.Column('error_logs', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )

    # 7. scrape_run_competitors
    op.create_table('scrape_run_competitors',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('scrape_run_id', sa.String(), nullable=False),
        sa.Column('business_id', sa.String(), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False, server_default="PENDING"),
        sa.Column('posts_discovered', sa.Integer(), nullable=False, server_default="0"),
        sa.Column('new_posts', sa.Integer(), nullable=False, server_default="0"),
        sa.Column('duplicates_skipped', sa.Integer(), nullable=False, server_default="0"),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['business_id'], ['business_profiles.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['scrape_run_id'], ['scrape_runs.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )

    # 8. scrape_observations
    op.create_table('scrape_observations',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('scrape_run_competitor_id', sa.String(), nullable=False),
        sa.Column('post_id', sa.String(), nullable=False),
        sa.Column('is_new', sa.Boolean(), nullable=False, server_default="0"),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['post_id'], ['posts.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['scrape_run_competitor_id'], ['scrape_run_competitors.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_scrape_observations_post_id'), 'scrape_observations', ['post_id'], unique=False)
    op.create_index(op.f('ix_scrape_observations_scrape_run_competitor_id'), 'scrape_observations', ['scrape_run_competitor_id'], unique=False)

    # 9. ai_analyses
    op.create_table('ai_analyses',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('post_id', sa.String(), nullable=False),
        sa.Column('provider', sa.String(length=50), nullable=False),
        sa.Column('model_name', sa.String(length=100), nullable=False),
        sa.Column('topic', sa.String(length=255), nullable=True),
        sa.Column('subtopic', sa.String(length=255), nullable=True),
        sa.Column('keywords', sa.JSON(), nullable=True),
        sa.Column('content_type', sa.String(length=100), nullable=True),
        sa.Column('cta_type', sa.String(length=100), nullable=True),
        sa.Column('offer_info', sa.String(length=255), nullable=True), 
        sa.Column('confidence', sa.Float(), nullable=True),
        sa.Column('raw_analysis', sa.JSON(), nullable=True),
        sa.Column('analyzed_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['post_id'], ['posts.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('post_id', name='ai_analyses_post_id_key')
    )
    op.create_index(op.f('ix_ai_analyses_post_id'), 'ai_analyses', ['post_id'], unique=False)

    # 10. generated_content
    op.create_table('generated_content',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('project_id', sa.String(), nullable=False),
        sa.Column('topic', sa.String(length=255), nullable=False),
        sa.Column('generated_idea', sa.Text(), nullable=False),
        sa.Column('full_copy', sa.Text(), nullable=True),
        sa.Column('keywords', sa.JSON(), nullable=True),
        sa.Column('cta', sa.String(length=255), nullable=True),
        sa.Column('image_concept', sa.Text(), nullable=True),
        sa.Column('provider', sa.String(length=50), nullable=False),
        sa.Column('model_name', sa.String(length=100), nullable=False),
        sa.Column('fingerprint', sa.String(length=255), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=False, server_default="QUEUED"),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('fingerprint', name='generated_content_fingerprint_key')
    )
    op.create_index(op.f('ix_generated_content_project_id'), 'generated_content', ['project_id'], unique=False)

def downgrade() -> None:
    op.drop_table('generated_content')
    op.drop_table('ai_analyses')
    op.drop_table('scrape_observations')
    op.drop_table('scrape_run_competitors')
    op.drop_table('scrape_runs')
    op.drop_table('post_media')
    op.drop_table('posts')
    op.drop_table('project_competitors')
    op.drop_table('projects')
    op.drop_table('business_profiles')
