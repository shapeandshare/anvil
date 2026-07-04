"""Add catalog_identities table and ModelRef columns to operational tables.

Greenfield schema change (ADR-032 / spec 064). Creates the transactional
dedup guard table and adds the registry_model_name + registry_model_version
column pairs that replace external_model_id FKs.

Revision ID: 012_add_catalog_identities_and_modelref
Revises: 011
Create Date: 2026-07-03
"""
revision: str = "012_add_catalog_identities_and_modelref"
down_revision: str | None = "011"
branch_labels: str | None = None
depends_on: str | None = None

from alembic import op
import sqlalchemy as sa


def upgrade() -> None:
    # catalog_identities — transactional dedup guard (FR-005)
    op.create_table(
        "catalog_identities",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("source_type", sa.String(20), nullable=False),
        sa.Column("source_identifier", sa.String(255), nullable=False),
        sa.Column("revision_sha", sa.String(255), nullable=False),
        sa.Column("registry_model_name", sa.String(255), nullable=False),
        sa.Column("registry_model_version", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "source_type",
            "source_identifier",
            "revision_sha",
            name="uq_catalog_identity_triple",
        ),
    )

    # Add ModelRef columns to operational tables (FR-006)
    # model_import_jobs
    op.add_column(
        "model_import_jobs",
        sa.Column("registry_model_name", sa.String(255), nullable=True),
    )
    op.add_column(
        "model_import_jobs",
        sa.Column("registry_model_version", sa.Integer(), nullable=True),
    )

    # asset_download_jobs
    op.add_column(
        "asset_download_jobs",
        sa.Column("registry_model_name", sa.String(255), nullable=True),
    )
    op.add_column(
        "asset_download_jobs",
        sa.Column("registry_model_version", sa.Integer(), nullable=True),
    )

    # model_assets
    op.add_column(
        "model_assets",
        sa.Column("registry_model_name", sa.String(255), nullable=False, server_default=""),
    )
    op.add_column(
        "model_assets",
        sa.Column("registry_model_version", sa.Integer(), nullable=False, server_default="0"),
    )

    # lora_adapters
    op.add_column(
        "lora_adapters",
        sa.Column("registry_model_name", sa.String(255), nullable=False, server_default=""),
    )
    op.add_column(
        "lora_adapters",
        sa.Column("registry_model_version", sa.Integer(), nullable=False, server_default="0"),
    )

    # evaluation_runs
    op.add_column(
        "evaluation_runs",
        sa.Column("model_name", sa.String(255), nullable=True),
    )
    op.add_column(
        "evaluation_runs",
        sa.Column("model_version", sa.Integer(), nullable=True),
    )
    op.add_column(
        "evaluation_runs",
        sa.Column("base_model_name", sa.String(255), nullable=True),
    )
    op.add_column(
        "evaluation_runs",
        sa.Column("base_model_version", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("catalog_identities")
    op.drop_column("model_import_jobs", "registry_model_version")
    op.drop_column("model_import_jobs", "registry_model_name")
    op.drop_column("asset_download_jobs", "registry_model_version")
    op.drop_column("asset_download_jobs", "registry_model_name")
    op.drop_column("model_assets", "registry_model_version")
    op.drop_column("model_assets", "registry_model_name")
    op.drop_column("lora_adapters", "registry_model_version")
    op.drop_column("lora_adapters", "registry_model_name")
    op.drop_column("evaluation_runs", "base_model_version")
    op.drop_column("evaluation_runs", "base_model_name")
    op.drop_column("evaluation_runs", "model_version")
    op.drop_column("evaluation_runs", "model_name")