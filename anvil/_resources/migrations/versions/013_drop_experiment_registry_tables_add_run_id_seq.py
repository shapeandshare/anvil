"""Drop experiments, registered_models, model_versions tables; add run_id_seq table."""

import sqlalchemy as sa
from alembic import op

revision: str = "013"
down_revision: str | None = "011"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.drop_table("model_versions")
    op.drop_table("registered_models")
    op.drop_table("experiments")
    op.create_table(
        "run_id_seq",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("next_id", sa.Integer(), nullable=False, server_default=sa.text("1")),
    )
    op.execute("INSERT INTO run_id_seq (next_id) VALUES (1)")


def downgrade() -> None:
    op.drop_table("run_id_seq")
    op.create_table(
        "experiments",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("mlflow_run_id", sa.String(255), nullable=True, unique=True),
        sa.Column("run_name", sa.String(255), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column(
            "config_id",
            sa.Integer(),
            sa.ForeignKey("training_configs.id"),
            nullable=True,
        ),
        sa.Column(
            "dataset_id", sa.Integer(), sa.ForeignKey("datasets.id"), nullable=True
        ),
        sa.Column("corpus_id", sa.Integer(), nullable=True),
        sa.Column("input_digest", sa.String(64), nullable=True),
        sa.Column("input_role", sa.String(20), nullable=True),
        sa.Column("engine_backend", sa.String(16), nullable=True),
        sa.Column("device", sa.String(16), nullable=True),
        sa.Column("execution_backend", sa.String(32), nullable=True),
        sa.Column("remote_job_id", sa.String(128), nullable=True),
        sa.Column("final_loss", sa.Float(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("generated_samples", sa.Text(), nullable=True),
        sa.Column("error_message", sa.String(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "registered_models",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(255), nullable=False, unique=True),
        sa.Column("description", sa.String(1000), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "model_versions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "model_id",
            sa.Integer(),
            sa.ForeignKey("registered_models.id"),
            nullable=False,
        ),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column(
            "experiment_id",
            sa.Integer(),
            sa.ForeignKey("experiments.id"),
            nullable=False,
        ),
        sa.Column("dataset_name", sa.String(255), nullable=True),
        sa.Column("artifact_path", sa.String(500), nullable=False),
        sa.Column("final_loss", sa.Float(), nullable=True),
        sa.Column("hyperparameters_json", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("model_id", "version"),
    )
