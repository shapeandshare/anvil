"""Add governance: provenance columns, license_catalog, audit_events.

Adds five provenance column pairs to the ``datasets`` and ``corpora``
tables (source_description, license_id FK, attribution_text, origin,
parent_provenance_ref), creates the ``license_catalog`` and
``audit_events`` tables with indexes, and backfills existing rows.
"""

revision: str = "014"
down_revision: str | None = "013"
branch_labels: str | None = None
depends_on: str | None = None

from alembic import op
import sqlalchemy as sa


def _provenance_columns() -> list[sa.Column]:
    """Return the list of provenance columns shared by datasets & corpora."""
    return [
        sa.Column("source_description", sa.String(1000), nullable=True),
        sa.Column("license_id", sa.Integer(), sa.ForeignKey("license_catalog.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("attribution_text", sa.String(1000), nullable=True),
        sa.Column("origin", sa.String(20), nullable=False, server_default="user"),
        sa.Column("parent_provenance_ref", sa.Integer(), nullable=True),
    ]


def upgrade() -> None:
    # ── 1. License catalog ──────────────────────────────────────────────
    op.create_table(
        "license_catalog",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("identifier", sa.String(100), nullable=False),
        sa.Column("display_name", sa.String(255), nullable=False),
        sa.Column("requires_attribution", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("redistribution_allowed", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("is_own_content_sentinel", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("identifier"),
    )

    # ── 2. Audit events ─────────────────────────────────────────────────
    op.create_table(
        "audit_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("action_type", sa.String(50), nullable=False),
        sa.Column("target_type", sa.String(50), nullable=False),
        sa.Column("target_id", sa.String(100), nullable=True),
        sa.Column("actor", sa.String(255), nullable=False),
        sa.Column("outcome", sa.String(20), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("params_json", sa.Text(), nullable=True),
        sa.Column("event_timestamp", sa.DateTime(), nullable=False),
        sa.Column("prev_hash", sa.String(64), nullable=False),
        sa.Column("entry_hash", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("sequence"),
        sa.UniqueConstraint("entry_hash"),
    )
    op.create_index("ix_audit_events_action_type", "audit_events", ["action_type"])
    op.create_index("ix_audit_events_target_type", "audit_events", ["target_type"])
    op.create_index("ix_audit_events_sequence", "audit_events", ["sequence"])

    # ── 3. Provenance columns on datasets ───────────────────────────────
    for col in _provenance_columns():
        op.add_column("datasets", col)

    # ── 4. Provenance columns on corpora ────────────────────────────────
    for col in _provenance_columns():
        op.add_column("corpora", col)

    # ── 5. Backfill existing rows ───────────────────────────────────────
    # Demo rows: set origin="bundled"
    op.execute(
        "UPDATE datasets SET origin = 'bundled' WHERE name LIKE 'Demo - %'"
    )
    op.execute(
        "UPDATE corpora SET origin = 'bundled' WHERE name LIKE 'Demo - %'"
    )


def downgrade() -> None:
    # Reversed order: drop columns, then tables.
    # Provenance columns from corpora
    for col in reversed(_provenance_columns()):
        op.drop_column("corpora", col.name)

    # Provenance columns from datasets
    for col in reversed(_provenance_columns()):
        op.drop_column("datasets", col.name)

    # Audit events
    op.drop_index("ix_audit_events_sequence", table_name="audit_events")
    op.drop_index("ix_audit_events_target_type", table_name="audit_events")
    op.drop_index("ix_audit_events_action_type", table_name="audit_events")
    op.drop_table("audit_events")

    # License catalog
    op.drop_table("license_catalog")