from sqlalchemy import Boolean, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from anvil.db.base import Base, TimestampMixin


class Sample(Base, TimestampMixin):
    __tablename__ = "samples"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    dataset_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False, index=True
    )
    index: Mapped[int] = mapped_column(Integer, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    length: Mapped[int] = mapped_column(Integer, nullable=False)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    is_removed: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    removed_by_op_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("curation_operations.id"), nullable=True
    )
    import_source_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("import_sources.id"), nullable=True
    )

    __table_args__ = (
        Index("ix_samples_dataset_index", "dataset_id", "index"),
        Index("ix_samples_dataset_hash", "dataset_id", "content_hash"),
        Index("ix_samples_dataset_length", "dataset_id", "length"),
    )


class CurationOperation(Base, TimestampMixin):
    __tablename__ = "curation_operations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    dataset_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False, index=True
    )
    operation_type: Mapped[str] = mapped_column(String(50), nullable=False)
    parameters: Mapped[str | None] = mapped_column(Text, nullable=True)
    sample_count_before: Mapped[int] = mapped_column(Integer, nullable=False)
    sample_count_after: Mapped[int] = mapped_column(Integer, nullable=False)


class ImportSource(Base, TimestampMixin):
    __tablename__ = "import_sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    dataset_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False, index=True
    )
    filename: Mapped[str] = mapped_column(String(500), nullable=False)
    format: Mapped[str] = mapped_column(String(20), nullable=False)
    row_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)