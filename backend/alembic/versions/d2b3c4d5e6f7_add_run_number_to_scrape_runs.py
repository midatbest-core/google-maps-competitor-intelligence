"""add run_number to scrape_runs

Revision ID: d2b3c4d5e6f7
Revises: c1a2b3d4e5f6
Create Date: 2026-11-16 22:06:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd2b3c4d5e6f7'
down_revision = 'c1a2b3d4e5f6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Use execute with IF NOT EXISTS for complete idempotency
    op.execute("ALTER TABLE scrape_runs ADD COLUMN IF NOT EXISTS run_number INTEGER;")
    
    # Backfill existing scrape_runs per project with sequential numbering based on created_at
    op.execute("""
        WITH numbered AS (
            SELECT id, ROW_NUMBER() OVER (PARTITION BY project_id ORDER BY created_at ASC) as seq
            FROM scrape_runs
        )
        UPDATE scrape_runs
        SET run_number = numbered.seq
        FROM numbered
        WHERE scrape_runs.id = numbered.id AND scrape_runs.run_number IS NULL;
    """)
    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_scrape_runs_project_run_number ON scrape_runs (project_id, run_number);")


def downgrade() -> None:
    op.drop_column('scrape_runs', 'run_number')
