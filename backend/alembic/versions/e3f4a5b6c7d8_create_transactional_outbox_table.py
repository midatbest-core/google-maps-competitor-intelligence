"""create transactional outbox table

Revision ID: e3f4a5b6c7d8
Revises: d2b3c4d5e6f7
Create Date: 2026-11-16 23:48:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e3f4a5b6c7d8'
down_revision = 'd2b3c4d5e6f7'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS outbox_messages (
            id VARCHAR PRIMARY KEY,
            event_type VARCHAR(100) NOT NULL,
            payload JSON NOT NULL,
            status VARCHAR(50) NOT NULL DEFAULT 'PENDING',
            attempts INTEGER NOT NULL DEFAULT 0,
            max_attempts INTEGER NOT NULL DEFAULT 5,
            last_attempt_at TIMESTAMP WITH TIME ZONE,
            next_attempt_at TIMESTAMP WITH TIME ZONE,
            claimed_at TIMESTAMP WITH TIME ZONE,
            claimed_until TIMESTAMP WITH TIME ZONE,
            claim_token VARCHAR(64),
            dispatched_at TIMESTAMP WITH TIME ZONE,
            error_message TEXT,
            created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
        );
    """)
    op.execute("ALTER TABLE outbox_messages ADD COLUMN IF NOT EXISTS claimed_at TIMESTAMP WITH TIME ZONE;")
    op.execute("ALTER TABLE outbox_messages ADD COLUMN IF NOT EXISTS claimed_until TIMESTAMP WITH TIME ZONE;")
    op.execute("ALTER TABLE outbox_messages ADD COLUMN IF NOT EXISTS claim_token VARCHAR(64);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_outbox_messages_event_type ON outbox_messages (event_type);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_outbox_messages_status ON outbox_messages (status);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_outbox_messages_next_attempt_at ON outbox_messages (next_attempt_at);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_outbox_messages_claimed_until ON outbox_messages (claimed_until);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_outbox_messages_claim_token ON outbox_messages (claim_token);")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS outbox_messages CASCADE;")
