"""add scrape_run heartbeat and outbox claim_token

Revision ID: f5a6b7c8d9e0
Revises: e3f4a5b6c7d8
Create Date: 2026-11-17 00:40:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f5a6b7c8d9e0'
down_revision = 'e3f4a5b6c7d8'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Add heartbeat_at to scrape_runs
    op.execute("ALTER TABLE scrape_runs ADD COLUMN IF NOT EXISTS heartbeat_at TIMESTAMP WITH TIME ZONE;")
    op.execute("CREATE INDEX IF NOT EXISTS ix_scrape_runs_heartbeat_at ON scrape_runs (heartbeat_at);")

    # 2. Add claim_token to outbox_messages (idempotent in case outbox was created with it)
    op.execute("ALTER TABLE outbox_messages ADD COLUMN IF NOT EXISTS claim_token VARCHAR(64);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_outbox_messages_claim_token ON outbox_messages (claim_token);")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_outbox_messages_claim_token;")
    op.execute("ALTER TABLE outbox_messages DROP COLUMN IF EXISTS claim_token;")
    op.execute("DROP INDEX IF EXISTS ix_scrape_runs_heartbeat_at;")
    op.execute("ALTER TABLE scrape_runs DROP COLUMN IF EXISTS heartbeat_at;")
