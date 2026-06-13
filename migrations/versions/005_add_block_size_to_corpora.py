"""Rev 005: Add block_size column to corpora table."""
from __future__ import annotations

revision = "005"
down_revision = "004"
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.add_column(
        "corpora",
        sa.Column("block_size", sa.Integer(), nullable=False, server_default="16"),
    )


def downgrade():
    op.drop_column("corpora", "block_size")