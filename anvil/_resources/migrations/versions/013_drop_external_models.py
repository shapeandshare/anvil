"""Rev 013: Drop external_models table (SC-006 / FR-007).

Removes the legacy ``external_models`` table.  FK columns on
``lora_adapters`` and ``evaluation_runs`` are left as nullable
integer columns (SQLite ignores dead FK declarations; they cause
no runtime issues).  The ``external_model_id`` column is removed
from ``model_import_jobs`` since that path is fully migrated to
ModelRef columns.

Revision ID: 013_drop_external_models
Revises: 012_add_catalog_identities_and_modelref
Create Date: 2026-07-03
"""

revision: str = "013_drop_external_models"
down_revision: str | None = "012_add_catalog_identities_and_modelref"
branch_labels: str | None = None
depends_on: str | None = None

from alembic import op
import sqlalchemy as sa


def upgrade() -> None:
    # Remove the FK column from model_import_jobs first, while
    # external_models still exists (batch_alter_table recreates
    # FK references and needs the target table present).
    with op.batch_alter_table("model_import_jobs") as batch_op:
        batch_op.drop_column("external_model_id")

    # Then drop the external_models table.  FK declarations on
    # lora_adapters and evaluation_runs become dead schema in
    # SQLite — harmless because FK enforcement is off by default.
    op.drop_table("external_models")


def downgrade() -> None:
    # Recreate external_models table
    op.create_table(
        "external_models",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("display_name", sa.String(255), nullable=False),
        sa.Column("source_type", sa.String(20), nullable=False),
        sa.Column("source_identifier", sa.String(255), nullable=False),
        sa.Column("architecture_family", sa.String(100), nullable=False),
        sa.Column("parameter_count", sa.Integer(), nullable=False),
        sa.Column("license", sa.String(100), nullable=False),
        sa.Column("tokenizer_family", sa.String(100), nullable=False),
        sa.Column("revision_sha", sa.String(255), nullable=False),
        sa.Column("runnable_status", sa.String(20), nullable=False),
        sa.Column("runnable_reason", sa.Text(), nullable=True),
        sa.Column("asset_availability", sa.String(20), nullable=False),
        sa.Column("config_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )

    # Restore model_import_jobs.external_model_id
    # Must use batch_alter_table because SQLite requires it when
    # adding columns with FK references.
    with op.batch_alter_table("model_import_jobs") as batch_op:
        batch_op.add_column(
            sa.Column("external_model_id", sa.Integer(), nullable=True),
        )