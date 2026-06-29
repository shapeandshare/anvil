"""Add model_assets, asset_download_jobs, user_secrets tables.

Revision ID: 05e6dc15c1c0
Revises: 005
Create Date: 2026-06-28
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision: str = "05e6dc15c1c0"
down_revision: str | None = "005"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    """Add three new tables for model asset storage (spec 042)."""
    op.create_table(
        "user_secrets",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.String(length=255), nullable=False),
        sa.Column("key", sa.String(length=100), nullable=False),
        sa.Column("encrypted_value", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "key", name="uq_user_secrets_user_key"),
    )
    op.create_table(
        "asset_download_jobs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("external_model_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("error_code", sa.String(length=50), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.ForeignKeyConstraint(
            ["external_model_id"], ["external_models.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "model_assets",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("external_model_id", sa.Integer(), nullable=False),
        sa.Column("asset_type", sa.String(length=20), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("storage_path", sa.String(length=512), nullable=True),
        sa.Column("sha256", sa.String(length=64), nullable=True),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("downloaded_bytes", sa.Integer(), nullable=False),
        sa.Column("source_url", sa.String(length=1024), nullable=True),
        sa.Column("format", sa.String(length=50), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.ForeignKeyConstraint(
            ["external_model_id"], ["external_models.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    """Revert by dropping the three new tables."""
    op.drop_table("model_assets")
    op.drop_table("asset_download_jobs")
    op.drop_table("user_secrets")