"""Rev 003: Add corpus_id to training_configs."""

revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.add_column(
        "training_configs",
        sa.Column(
            "corpus_id", sa.Integer(), sa.ForeignKey("corpora.id"), nullable=True
        ),
    )


def downgrade():
    op.drop_column("training_configs", "corpus_id")