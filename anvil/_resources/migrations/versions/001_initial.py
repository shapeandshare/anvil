"""Rev 001: Squashed initial migration — canonical schema.

Combines all prior migrations (001–014) into a single initial
migration that creates the final canonical schema. Skips tables
that were created and later dropped (experiments, registered_models,
model_versions) since the project has zero deployments.
"""

revision: str = "001"
down_revision: str | None = None
branch_labels: str | None = None
depends_on: str | None = None

from alembic import op
import sqlalchemy as sa


def _provenance_columns_named(table: str) -> list[sa.Column]:
    """Return provenance columns with explicit FK constraint name for *table*."""
    return [
        sa.Column("source_description", sa.String(1000), nullable=True),
        sa.Column(
            "license_id",
            sa.Integer(),
            sa.ForeignKey(
                "license_catalog.id",
                ondelete="RESTRICT",
                name=f"fk_{table}_license_id",
            ),
            nullable=True,
        ),
        sa.Column("attribution_text", sa.String(1000), nullable=True),
        sa.Column("origin", sa.String(20), nullable=False, server_default="user"),
        sa.Column("parent_provenance_ref", sa.Integer(), nullable=True),
    ]


def upgrade() -> None:
    # ── 1. License catalog (no FK dependencies) ─────────────────────────
    op.create_table(
        "license_catalog",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("identifier", sa.String(100), nullable=False),
        sa.Column("display_name", sa.String(255), nullable=False),
        sa.Column(
            "requires_attribution", sa.Boolean(), nullable=False, server_default=sa.text("0")
        ),
        sa.Column(
            "redistribution_allowed", sa.Boolean(), nullable=False, server_default=sa.text("1")
        ),
        sa.Column(
            "is_own_content_sentinel", sa.Boolean(), nullable=False, server_default=sa.text("0")
        ),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("identifier"),
    )

    # ── 2. Datasets ─────────────────────────────────────────────────────
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
        sa.Column("sample_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_size_bytes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("curation_version", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(20), nullable=False, server_default="empty"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    # Provenance columns on datasets (SQLite: use batch mode for FK)
    with op.batch_alter_table("datasets") as batch_op:
        for col in _provenance_columns_named("datasets"):
            batch_op.add_column(col)

    # ── 3. Corpora ──────────────────────────────────────────────────────
    op.create_table(
        "corpora",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(255), nullable=False, unique=True),
        sa.Column("description", sa.String(1000), nullable=True),
        sa.Column("root_path", sa.String(500), nullable=False),
        sa.Column("include_patterns", sa.Text(), nullable=True),
        sa.Column("exclude_patterns", sa.Text(), nullable=True),
        sa.Column("chunking_strategy", sa.String(20), nullable=False, server_default="windowed"),
        sa.Column("chunk_overlap", sa.Float(), nullable=False, server_default="0.5"),
        sa.Column("block_size", sa.Integer(), nullable=False, server_default="16"),
        sa.Column("file_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("document_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("language_map", sa.Text(), nullable=True),
        sa.Column("errors", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    # parent_id FK (self-referencing) + provenance on corpora
    with op.batch_alter_table("corpora") as batch_op:
        batch_op.add_column(sa.Column("parent_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_corpora_parent_id", "corpora", ["parent_id"], ["id"], ondelete="SET NULL"
        )
        for col in _provenance_columns_named("corpora"):
            batch_op.add_column(col)

    # ── 4. Corpus files (FK → corpora) ──────────────────────────────────
    op.create_table(
        "corpus_files",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("corpus_id", sa.Integer(), sa.ForeignKey("corpora.id", ondelete="CASCADE"), nullable=False),
        sa.Column("relative_path", sa.String(1000), nullable=False),
        sa.Column("language", sa.String(50), nullable=True),
        sa.Column("line_count", sa.Integer(), nullable=True),
        sa.Column("char_count", sa.Integer(), nullable=True),
        sa.Column("chunk_count", sa.Integer(), nullable=True),
        sa.Column("encoding", sa.String(20), nullable=True),
        sa.Column("size_bytes", sa.Integer(), nullable=True),
        sa.Column("last_modified", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("corpus_id", "relative_path"),
    )

    # ── 5. Training configs (FK → datasets, corpora) ────────────────────
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
        sa.Column("dataset_id", sa.Integer(), sa.ForeignKey("datasets.id"), nullable=True),
        sa.Column("corpus_id", sa.Integer(), sa.ForeignKey("corpora.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    # ── 6. Import sources (FK → datasets) ───────────────────────────────
    op.create_table(
        "import_sources",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("dataset_id", sa.Integer(), sa.ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("filename", sa.String(500), nullable=False),
        sa.Column("format", sa.String(20), nullable=False),
        sa.Column("row_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    # ── 7. Curation operations (FK → datasets) ──────────────────────────
    op.create_table(
        "curation_operations",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("dataset_id", sa.Integer(), sa.ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("operation_type", sa.String(50), nullable=False),
        sa.Column("parameters", sa.Text(), nullable=True),
        sa.Column("sample_count_before", sa.Integer(), nullable=False),
        sa.Column("sample_count_after", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    # ── 8. Samples (FK → datasets, curation_operations, import_sources) ─
    op.create_table(
        "samples",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("dataset_id", sa.Integer(), sa.ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("index", sa.Integer(), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("length", sa.Integer(), nullable=False),
        sa.Column("file_path", sa.String(500), nullable=False),
        sa.Column("is_removed", sa.Boolean(), server_default="0", nullable=False, index=True),
        sa.Column("removed_by_op_id", sa.Integer(), sa.ForeignKey("curation_operations.id"), nullable=True),
        sa.Column("import_source_id", sa.Integer(), sa.ForeignKey("import_sources.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_samples_dataset_index", "samples", ["dataset_id", "index"])
    op.create_index("ix_samples_dataset_hash", "samples", ["dataset_id", "content_hash"])
    op.create_index("ix_samples_dataset_length", "samples", ["dataset_id", "length"])

    # ── 9. Audit events (no FK dependencies) ────────────────────────────
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

    # ── 10. Run ID sequence (no FK dependencies) ────────────────────────
    op.create_table(
        "run_id_seq",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("next_id", sa.Integer(), nullable=False, server_default=sa.text("1")),
    )
    op.execute("INSERT INTO run_id_seq (next_id) VALUES (1)")


def downgrade() -> None:
    op.drop_table("run_id_seq")
    op.drop_index("ix_audit_events_sequence", table_name="audit_events")
    op.drop_index("ix_audit_events_target_type", table_name="audit_events")
    op.drop_index("ix_audit_events_action_type", table_name="audit_events")
    op.drop_table("audit_events")
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
