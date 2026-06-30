"""Rev 008: Add ``key_id`` column to ``user_secrets`` (spec 058).

Adds an indexed ``key_id`` column enabling efficient per-key queries
for the re-encryption sweep and expiry gate. Greenfield — no pre-existing
data requiring a backfill.
"""

import sqlalchemy as sa
from alembic import op

revision: str = "008"
down_revision: str | None = "007"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column(
        "user_secrets",
        sa.Column("key_id", sa.String(36), nullable=False, server_default=""),
    )
    op.create_index("ix_user_secrets_key_id", "user_secrets", ["key_id"])


def downgrade() -> None:
    op.drop_index("ix_user_secrets_key_id", table_name="user_secrets")
    op.drop_column("user_secrets", "key_id")
