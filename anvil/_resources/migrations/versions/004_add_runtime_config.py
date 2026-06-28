"""Rev 004: Create runtime_config table.

Creates the ``runtime_config`` table for the config CRUD UI
(feature 037-T046).  Stores per-instance runtime configuration
overrides with key, value, apply_class, and automatic timestamps.
"""

revision: str = "004"
down_revision: str | None = "003"
branch_labels: str | None = None
depends_on: str | None = None

import sqlalchemy as sa
from alembic import op


def upgrade() -> None:
    op.create_table(
        "runtime_config",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("key", sa.String(100), nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("apply_class", sa.String(20), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("key"),
    )
    op.create_index("ix_runtime_config_key", "runtime_config", ["key"])


def downgrade() -> None:
    op.drop_index("ix_runtime_config_key", table_name="runtime_config")
    op.drop_table("runtime_config")
