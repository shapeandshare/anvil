"""Rev 013: Drop external_models table (SC-006 / FR-007).

Removes the legacy ``external_models`` table and the now-unused
``external_model_id`` column from ``model_import_jobs``.  The
``external_model_id`` FK on ``lora_adapters`` and ``evaluation_runs``
is also dropped (columns remain in the ORM with nullable=True for
backward compatibility with existing records).

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
    # Drop FK-dependent columns first (SQLite requires this order)
    # lora_adapters.external_model_id - drop FK, keep nullable column
    op.drop_constraint(
        "lora_adapters_ibfk_1", "lora_adapters", type_="foreignkey"
    )

    # evaluation_runs.external_model_id and base_external_model_id FKs
    op.drop_constraint(
        "evaluation_runs_ibfk_1", "evaluation_runs", type_="foreignkey"
    )
    op.drop_constraint(
        "evaluation_runs_ibfk_2", "evaluation_runs", type_="foreignkey"
    )

    # model_import_jobs.external_model_id FK
    op.drop_constraint(
        "model_import_jobs_ibfk_1", "model_import_jobs", type_="foreignkey"
    )
    op.drop_column("model_import_jobs", "external_model_id")

    # Drop the external_models table
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
    op.add_column(
        "model_import_jobs",
        sa.Column(
            "external_model_id",
            sa.Integer(),
            sa.ForeignKey("external_models.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )

    # Restore FKs (SQLite doesn't enforce FK constraints by default,
    # but we recreate the schema declarations)
    op.create_foreign_key(
        "lora_adapters_ibfk_1",
        "lora_adapters", "external_models",
        ["external_model_id"], ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "evaluation_runs_ibfk_1",
        "evaluation_runs", "external_models",
        ["external_model_id"], ["id"],
    )
    op.create_foreign_key(
        "evaluation_runs_ibfk_2",
        "evaluation_runs", "external_models",
        ["base_external_model_id"], ["id"],
    )
    op.create_foreign_key(
        "model_import_jobs_ibfk_1",
        "model_import_jobs", "external_models",
        ["external_model_id"], ["id"],
        ondelete="SET NULL",
    )