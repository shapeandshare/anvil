"""Add ``teaching_sessions`` table (spec 055).

Adds the ``teaching_sessions`` table for the Interactive Teaching Loop
feature. Unlike other model-reference tables in the schema,
``teaching_sessions`` does **not** carry an ``ExternalModel`` FK —
it chains on the native integer experiment id.

Greenfield — no pre-existing data requiring a backfill.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "011"
down_revision: str | None = "010"
branch_labels: str | None = None
depends_on: str | None = None

_CURRENT_TS = sa.text("(CURRENT_TIMESTAMP)")
"""Reusable default for created_at / updated_at columns."""


def upgrade() -> None:
    """Create the ``teaching_sessions`` table."""
    op.create_table(
        "teaching_sessions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("seed_experiment_id", sa.Integer(), nullable=True),
        sa.Column("current_base_experiment_id", sa.Integer(), nullable=True),
        sa.Column(
            "status",
            sa.String(16),
            nullable=False,
            server_default=sa.text("'draft'"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=_CURRENT_TS,
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=_CURRENT_TS,
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_teaching_sessions")),
    )
    op.create_index(
        "idx_teaching_sessions_status",
        "teaching_sessions",
        ["status"],
    )
    op.create_index(
        "idx_teaching_sessions_created",
        "teaching_sessions",
        ["created_at"],
    )


def downgrade() -> None:
    """Drop the ``teaching_sessions`` table and its indexes."""
    op.drop_index("idx_teaching_sessions_created", table_name="teaching_sessions")
    op.drop_index("idx_teaching_sessions_status", table_name="teaching_sessions")
    op.drop_table("teaching_sessions")
