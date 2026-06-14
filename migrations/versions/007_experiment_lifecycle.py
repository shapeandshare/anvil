"""Rev 007: Experiment lifecycle fields and status backfill."""

revision: str = "007"
down_revision: str | None = "12a4027155f0"
branch_labels: str | None = None
depends_on: str | None = None

import sqlalchemy as sa
from alembic import op


def upgrade() -> None:
    op.add_column(
        "experiments", sa.Column("run_name", sa.String(length=255), nullable=True)
    )
    op.add_column("experiments", sa.Column("corpus_id", sa.Integer(), nullable=True))
    op.add_column(
        "experiments", sa.Column("input_digest", sa.String(length=64), nullable=True)
    )
    op.add_column(
        "experiments", sa.Column("input_role", sa.String(length=20), nullable=True)
    )
    op.add_column(
        "experiments", sa.Column("engine_backend", sa.String(length=16), nullable=True)
    )
    op.add_column(
        "experiments", sa.Column("device", sa.String(length=16), nullable=True)
    )

    # Data backfill: terminal-status-preserving
    op.execute("UPDATE experiments SET status = 'finished' WHERE status = 'completed'")
    op.execute(
        "UPDATE experiments SET status = 'failed', error_message = 'legacy/unknown' WHERE status = 'pending'"
    )


def downgrade() -> None:
    op.drop_column("experiments", "device")
    op.drop_column("experiments", "engine_backend")
    op.drop_column("experiments", "input_role")
    op.drop_column("experiments", "input_digest")
    op.drop_column("experiments", "corpus_id")
    op.drop_column("experiments", "run_name")
