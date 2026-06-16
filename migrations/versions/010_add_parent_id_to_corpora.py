"""Rev 010: Add parent_id FK to corpora for corpus forking/versioning.

Enables creating new corpus variants (forks) from an existing corpus,
with the ability to override chunking parameters while preserving lineage.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "010"
down_revision: str | None = "009"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    with op.batch_alter_table("corpora") as batch_op:
        batch_op.add_column(
            sa.Column("parent_id", sa.Integer(), nullable=True),
        )
        batch_op.create_foreign_key(
            "fk_corpora_parent_id",
            "corpora",
            ["parent_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    with op.batch_alter_table("corpora") as batch_op:
        batch_op.drop_constraint("fk_corpora_parent_id", type_="foreignkey")
        batch_op.drop_column("parent_id")