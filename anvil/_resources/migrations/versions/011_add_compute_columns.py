"""Rev 011: Add execution_backend and remote_job_id to experiments.

Tracks which compute backend (local, remote-ssh, slurm, modal, aws-batch)
an experiment runs on, plus the remote job identifier for out-of-process
execution.
"""

import sqlalchemy as sa
from alembic import op

revision: str = "011"
down_revision: str | None = "010"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    with op.batch_alter_table("experiments") as batch_op:
        batch_op.add_column(
            sa.Column("execution_backend", sa.String(32), nullable=True),
        )
        batch_op.add_column(
            sa.Column("remote_job_id", sa.String(128), nullable=True),
        )


def downgrade() -> None:
    with op.batch_alter_table("experiments") as batch_op:
        batch_op.drop_column("remote_job_id")
        batch_op.drop_column("execution_backend")
