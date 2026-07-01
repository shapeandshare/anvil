"""Add ``lora_adapters`` table for LoRA fine-tuning adapter tracking (spec 044).

Adds a new table ``lora_adapters`` to track LoRA fine-tuning results
scoped to a base model. Greenfield — no pre-existing data requiring a
backfill.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "009"
down_revision: str | None = "008"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    """Create the ``lora_adapters`` table."""
    op.create_table(
        "lora_adapters",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("external_model_id", sa.Integer(), nullable=False),
        sa.Column("run_id", sa.Integer(), nullable=False),
        sa.Column("adapter_id", sa.String(length=255), nullable=False),
        sa.Column("label", sa.String(length=255), nullable=True),
        sa.Column("method", sa.String(length=20), nullable=False),
        sa.Column("storage_path", sa.String(length=512), nullable=False),
        sa.Column("lora_rank", sa.Integer(), nullable=False),
        sa.Column("lora_alpha", sa.Float(), nullable=False),
        sa.Column("lora_target_modules", sa.Text(), nullable=True),
        sa.Column("lora_dropout", sa.Float(), nullable=True),
        sa.Column("lora_bias", sa.String(length=20), nullable=True),
        sa.Column("final_loss", sa.Float(), nullable=True),
        sa.Column("final_step", sa.Integer(), nullable=True),
        sa.Column("merged_at", sa.DateTime(), nullable=True),
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
            "external_model_id",
            "adapter_id",
            name="uq_lora_adapters_model_adapter",
        ),
        sa.ForeignKeyConstraint(
            ["external_model_id"],
            ["external_models.id"],
            ondelete="CASCADE",
        ),
    )
    op.create_index(
        "ix_lora_adapters_external_model_id",
        "lora_adapters",
        ["external_model_id"],
    )


def downgrade() -> None:
    """Drop the ``lora_adapters`` table."""
    op.drop_table("lora_adapters")
