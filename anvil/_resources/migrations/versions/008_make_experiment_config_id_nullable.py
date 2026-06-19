"""Rev 008: Make experiment config_id nullable.

Experiments can be created without a pre-saved TrainingConfig row.
The hardcoded config_id=0 was causing FOREIGN KEY constraint failures.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "008"
down_revision: str | None = "007"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    with op.batch_alter_table("experiments") as batch_op:
        batch_op.alter_column("config_id", existing_type=sa.Integer(), nullable=True)


def downgrade() -> None:
    # Backfill NULL config_ids to a placeholder before making NOT NULL
    # (in practice this shouldn't happen — but the placeholder 0 will fail FK too)
    with op.batch_alter_table("experiments") as batch_op:
        batch_op.alter_column("config_id", existing_type=sa.Integer(), nullable=False)
