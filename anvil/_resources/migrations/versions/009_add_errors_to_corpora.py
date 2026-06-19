"""Rev 009: Add errors column to corpora table for persisting ingest warnings."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "009"
down_revision: str | None = "008"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column(
        "corpora",
        sa.Column("errors", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("corpora", "errors")
