"""Add ``evaluation_runs``, ``metric_deltas``, ``eval_samples`` tables (spec 054).

Adds three new tables for fine-tuned model evaluation:
- ``evaluation_runs`` — per-evaluation-run metadata and model references
- ``metric_deltas`` — per-metric base→fine-tuned comparison values
- ``eval_samples`` — per-prompt side-by-side sample outputs

Greenfield — no pre-existing data requiring a backfill.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "010"
down_revision: str | None = "009"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    """Create ``evaluation_runs``, ``metric_deltas``, and ``eval_samples`` tables."""
    # --- evaluation_runs ---
    op.create_table(
        "evaluation_runs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("external_model_id", sa.Integer(), nullable=False),
        sa.Column("base_external_model_id", sa.Integer(), nullable=True),
        sa.Column("adapter_id", sa.String(length=255), nullable=True),
        sa.Column("tokenizer_family", sa.String(length=100), nullable=False),
        sa.Column("base_tokenizer_family", sa.String(length=100), nullable=True),
        sa.Column("eval_dataset_name", sa.String(length=255), nullable=True),
        sa.Column(
            "status",
            sa.String(length=20),
            nullable=False,
            server_default=sa.text("'pending'"),
        ),
        sa.Column("mlflow_run_id", sa.String(length=255), nullable=True),
        sa.Column(
            "prompt_count", sa.Integer(), nullable=False, server_default=sa.text("0")
        ),
        sa.Column("meta", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["external_model_id"],
            ["external_models.id"],
        ),
        sa.ForeignKeyConstraint(
            ["base_external_model_id"],
            ["external_models.id"],
        ),
    )
    op.create_index(
        "ix_evaluation_runs_external_model_id", "evaluation_runs", ["external_model_id"]
    )
    op.create_index(
        "ix_evaluation_runs_base_external_model_id",
        "evaluation_runs",
        ["base_external_model_id"],
    )
    op.create_index("ix_evaluation_runs_status", "evaluation_runs", ["status"])
    op.create_index("ix_evaluation_runs_created_at", "evaluation_runs", ["created_at"])

    # --- metric_deltas ---
    op.create_table(
        "metric_deltas",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("evaluation_run_id", sa.Integer(), nullable=False),
        sa.Column("metric_name", sa.String(length=100), nullable=False),
        sa.Column("fine_tuned_value", sa.Float(), nullable=False),
        sa.Column("base_value", sa.Float(), nullable=False),
        sa.Column("delta", sa.Float(), nullable=False),
        sa.Column(
            "comparable", sa.Boolean(), nullable=False, server_default=sa.text("1")
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "evaluation_run_id", "metric_name", name="uq_metric_delta_per_run"
        ),
        sa.ForeignKeyConstraint(
            ["evaluation_run_id"],
            ["evaluation_runs.id"],
            ondelete="CASCADE",
        ),
    )
    op.create_index(
        "ix_metric_deltas_evaluation_run_id", "metric_deltas", ["evaluation_run_id"]
    )

    # --- eval_samples ---
    op.create_table(
        "eval_samples",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("evaluation_run_id", sa.Integer(), nullable=False),
        sa.Column("prompt_index", sa.Integer(), nullable=False),
        sa.Column("input", sa.Text(), nullable=False),
        sa.Column("base_output", sa.Text(), nullable=True),
        sa.Column("fine_tuned_output", sa.Text(), nullable=True),
        sa.Column("base_loss", sa.Float(), nullable=True),
        sa.Column("fine_tuned_loss", sa.Float(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "evaluation_run_id", "prompt_index", name="uq_sample_per_run"
        ),
        sa.ForeignKeyConstraint(
            ["evaluation_run_id"],
            ["evaluation_runs.id"],
            ondelete="CASCADE",
        ),
    )
    op.create_index(
        "ix_eval_samples_evaluation_run_id", "eval_samples", ["evaluation_run_id"]
    )


def downgrade() -> None:
    """Drop all three evaluation tables (respect FK ordering)."""
    op.drop_table("eval_samples")
    op.drop_table("metric_deltas")
    op.drop_table("evaluation_runs")
