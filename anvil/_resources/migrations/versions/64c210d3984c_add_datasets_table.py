"""Rev 003: Add missing tables from squashed 001 migration.

Creates tables that are defined in the ORM models but were
missing from the database (likely cleaned during test/dev DB
resets). Does NOT drop ``run_id_seq`` — it is used via raw SQL
in the training service and has no model class.

Created by autogenerate against a DB that was at rev 002 but
had been stripped of 001's tables.
"""

revision: str = "64c210d3984c"
down_revision: str | None = "002"
branch_labels: str | None = None
depends_on: str | None = None

import sqlalchemy as sa
from alembic import op


def upgrade() -> None:
    # ── License catalog ───────────────────────────────────────────────
    op.create_table(
        "license_catalog",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("identifier", sa.String(length=100), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=False),
        sa.Column("requires_attribution", sa.Boolean(), nullable=False),
        sa.Column("redistribution_allowed", sa.Boolean(), nullable=False),
        sa.Column("is_own_content_sentinel", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("identifier"),
    )

    # ── Datasets ──────────────────────────────────────────────────────
    op.create_table(
        "datasets",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.String(length=1000), nullable=True),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("file_path", sa.String(length=500), nullable=False),
        sa.Column("vocabulary_size", sa.Integer(), nullable=True),
        sa.Column("document_count", sa.Integer(), nullable=True),
        sa.Column("is_default", sa.Boolean(), nullable=False),
        sa.Column("sample_count", sa.Integer(), nullable=False),
        sa.Column("total_size_bytes", sa.Integer(), nullable=False),
        sa.Column("curation_version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("source_description", sa.String(length=1000), nullable=True),
        sa.Column("license_id", sa.Integer(), nullable=True),
        sa.Column("attribution_text", sa.String(length=1000), nullable=True),
        sa.Column("origin", sa.String(length=20), nullable=False),
        sa.Column("parent_provenance_ref", sa.Integer(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["license_id"], ["license_catalog.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )

    # ── Corpora ───────────────────────────────────────────────────────
    op.create_table(
        "corpora",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.String(length=1000), nullable=True),
        sa.Column("root_path", sa.String(length=500), nullable=False),
        sa.Column("include_patterns", sa.Text(), nullable=True),
        sa.Column("exclude_patterns", sa.Text(), nullable=True),
        sa.Column("chunking_strategy", sa.String(length=20), nullable=False),
        sa.Column("chunk_overlap", sa.Float(), nullable=False),
        sa.Column("block_size", sa.Integer(), nullable=False),
        sa.Column("parent_id", sa.Integer(), nullable=True),
        sa.Column("file_count", sa.Integer(), nullable=False),
        sa.Column("document_count", sa.Integer(), nullable=False),
        sa.Column("language_map", sa.Text(), nullable=True),
        sa.Column("errors", sa.Text(), nullable=True),
        sa.Column("source_description", sa.String(length=1000), nullable=True),
        sa.Column("license_id", sa.Integer(), nullable=True),
        sa.Column("attribution_text", sa.String(length=1000), nullable=True),
        sa.Column("origin", sa.String(length=20), nullable=False),
        sa.Column("parent_provenance_ref", sa.Integer(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["license_id"], ["license_catalog.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["parent_id"], ["corpora.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )

    # ── Corpus files ──────────────────────────────────────────────────
    op.create_table(
        "corpus_files",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("corpus_id", sa.Integer(), nullable=False),
        sa.Column("relative_path", sa.String(length=1000), nullable=False),
        sa.Column("language", sa.String(length=50), nullable=True),
        sa.Column("line_count", sa.Integer(), nullable=True),
        sa.Column("char_count", sa.Integer(), nullable=True),
        sa.Column("chunk_count", sa.Integer(), nullable=True),
        sa.Column("encoding", sa.String(length=20), nullable=True),
        sa.Column("size_bytes", sa.Integer(), nullable=True),
        sa.Column("last_modified", sa.DateTime(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["corpus_id"], ["corpora.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    # ── Training configs ──────────────────────────────────────────────
    op.create_table(
        "training_configs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=255), nullable=True),
        sa.Column("n_layer", sa.Integer(), nullable=False),
        sa.Column("n_embd", sa.Integer(), nullable=False),
        sa.Column("n_head", sa.Integer(), nullable=False),
        sa.Column("block_size", sa.Integer(), nullable=False),
        sa.Column("num_steps", sa.Integer(), nullable=False),
        sa.Column("learning_rate", sa.Float(), nullable=False),
        sa.Column("beta1", sa.Float(), nullable=False),
        sa.Column("beta2", sa.Float(), nullable=False),
        sa.Column("temperature", sa.Float(), nullable=False),
        sa.Column("dataset_id", sa.Integer(), nullable=True),
        sa.Column("corpus_id", sa.Integer(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["dataset_id"], ["datasets.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["corpus_id"], ["corpora.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )

    # ── Import sources ────────────────────────────────────────────────
    op.create_table(
        "import_sources",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("dataset_id", sa.Integer(), nullable=False),
        sa.Column("filename", sa.String(length=500), nullable=False),
        sa.Column("format", sa.String(length=20), nullable=False),
        sa.Column("row_count", sa.Integer(), nullable=False),
        sa.Column("error_count", sa.Integer(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["dataset_id"], ["datasets.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    # ── Curation operations ───────────────────────────────────────────
    op.create_table(
        "curation_operations",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("dataset_id", sa.Integer(), nullable=False),
        sa.Column("operation_type", sa.String(length=50), nullable=False),
        sa.Column("parameters", sa.Text(), nullable=True),
        sa.Column("sample_count_before", sa.Integer(), nullable=False),
        sa.Column("sample_count_after", sa.Integer(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["dataset_id"], ["datasets.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    # ── Samples ───────────────────────────────────────────────────────
    op.create_table(
        "samples",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("dataset_id", sa.Integer(), nullable=False),
        sa.Column("index", sa.Integer(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("length", sa.Integer(), nullable=False),
        sa.Column("file_path", sa.String(length=500), nullable=False),
        sa.Column("is_removed", sa.Boolean(), nullable=False),
        sa.Column("removed_by_op_id", sa.Integer(), nullable=True),
        sa.Column("import_source_id", sa.Integer(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["dataset_id"], ["datasets.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["import_source_id"], ["import_sources.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["removed_by_op_id"], ["curation_operations.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_samples_dataset_index", "samples", ["dataset_id", "index"])
    op.create_index(
        "ix_samples_dataset_hash", "samples", ["dataset_id", "content_hash"]
    )
    op.create_index("ix_samples_dataset_length", "samples", ["dataset_id", "length"])
    op.create_index(op.f("ix_samples_dataset_id"), "samples", ["dataset_id"])

    # ── Audit events ──────────────────────────────────────────────────
    op.create_table(
        "audit_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("action_type", sa.String(length=50), nullable=False),
        sa.Column("target_type", sa.String(length=50), nullable=False),
        sa.Column("target_id", sa.String(length=100), nullable=True),
        sa.Column("actor", sa.String(length=255), nullable=False),
        sa.Column("outcome", sa.String(length=20), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("params_json", sa.Text(), nullable=True),
        sa.Column("event_timestamp", sa.DateTime(), nullable=False),
        sa.Column("prev_hash", sa.String(length=64), nullable=False),
        sa.Column("entry_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("entry_hash"),
    )
    op.create_index(
        op.f("ix_audit_events_action_type"), "audit_events", ["action_type"]
    )
    op.create_index(
        op.f("ix_audit_events_sequence"), "audit_events", ["sequence"], unique=True
    )
    op.create_index(
        op.f("ix_audit_events_target_type"), "audit_events", ["target_type"]
    )

    # NOTE: run_id_seq is intentionally NOT dropped here.
    # It has no ORM model class — it is used via raw SQL in the
    # training service (allocate_experiment_id). Migration 001
    # already creates it; the autogenerate falsely flagged it
    # as "removed" because no model maps to it.


def downgrade() -> None:
    op.drop_index(op.f("ix_audit_events_target_type"), table_name="audit_events")
    op.drop_index(op.f("ix_audit_events_sequence"), table_name="audit_events")
    op.drop_index(op.f("ix_audit_events_action_type"), table_name="audit_events")
    op.drop_table("audit_events")
    op.drop_index(op.f("ix_samples_dataset_id"), table_name="samples")
    op.drop_index("ix_samples_dataset_length", table_name="samples")
    op.drop_index("ix_samples_dataset_hash", table_name="samples")
    op.drop_index("ix_samples_dataset_index", table_name="samples")
    op.drop_table("samples")
    op.drop_table("curation_operations")
    op.drop_table("import_sources")
    op.drop_table("training_configs")
    op.drop_table("corpus_files")
    op.drop_table("corpora")
    op.drop_table("datasets")
    op.drop_table("license_catalog")
