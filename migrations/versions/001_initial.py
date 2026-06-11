"""Rev 001: Create initial tables."""

revision = "001"
down_revision = None
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.create_table(
        "datasets",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(255), nullable=False, unique=True),
        sa.Column("description", sa.String(1000), nullable=True),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("file_path", sa.String(500), nullable=False),
        sa.Column("vocabulary_size", sa.Integer(), nullable=True),
        sa.Column("document_count", sa.Integer(), nullable=True),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "training_configs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(255), nullable=True),
        sa.Column("n_layer", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("n_embd", sa.Integer(), nullable=False, server_default="16"),
        sa.Column("n_head", sa.Integer(), nullable=False, server_default="4"),
        sa.Column("block_size", sa.Integer(), nullable=False, server_default="16"),
        sa.Column("num_steps", sa.Integer(), nullable=False, server_default="1000"),
        sa.Column("learning_rate", sa.Float(), nullable=False, server_default="0.01"),
        sa.Column("beta1", sa.Float(), nullable=False, server_default="0.85"),
        sa.Column("beta2", sa.Float(), nullable=False, server_default="0.99"),
        sa.Column("temperature", sa.Float(), nullable=False, server_default="0.5"),
        sa.Column("use_gpu", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("dataset_id", sa.Integer(), sa.ForeignKey("datasets.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "experiments",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("mlflow_run_id", sa.String(255), nullable=True, unique=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("config_id", sa.Integer(), sa.ForeignKey("training_configs.id"), nullable=False),
        sa.Column("dataset_id", sa.Integer(), sa.ForeignKey("datasets.id"), nullable=True),
        sa.Column("final_loss", sa.Float(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("generated_samples", sa.Text(), nullable=True),
        sa.Column("error_message", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade():
    op.drop_table("experiments")
    op.drop_table("training_configs")
    op.drop_table("datasets")