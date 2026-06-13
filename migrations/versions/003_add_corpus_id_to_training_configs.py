"""Rev 003: Add corpus_id to training_configs."""

revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa


def upgrade():
    with op.batch_alter_table("training_configs") as batch_op:
        batch_op.add_column(
            sa.Column("corpus_id", sa.Integer(), nullable=True),
        )
        batch_op.create_foreign_key(
            "fk_training_configs_corpus_id", "corpora", ["corpus_id"], ["id"],
        )


def downgrade():
    with op.batch_alter_table("training_configs") as batch_op:
        batch_op.drop_constraint("fk_training_configs_corpus_id", type_="foreignkey")
        batch_op.drop_column("corpus_id")