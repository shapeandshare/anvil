from __future__ import annotations

from sqlalchemy import Boolean, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from anvil.db.base import Base, TimestampMixin


class TrainingConfig(Base, TimestampMixin):
    __tablename__ = "training_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    n_layer: Mapped[int] = mapped_column(Integer, default=1)
    n_embd: Mapped[int] = mapped_column(Integer, default=16)
    n_head: Mapped[int] = mapped_column(Integer, default=4)
    block_size: Mapped[int] = mapped_column(Integer, default=16)
    num_steps: Mapped[int] = mapped_column(Integer, default=1000)
    learning_rate: Mapped[float] = mapped_column(Float, default=0.01)
    beta1: Mapped[float] = mapped_column(Float, default=0.85)
    beta2: Mapped[float] = mapped_column(Float, default=0.99)
    temperature: Mapped[float] = mapped_column(Float, default=0.5)
    use_gpu: Mapped[bool] = mapped_column(Boolean, default=False)
    dataset_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("datasets.id"), nullable=True
    )
    corpus_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("corpora.id"), nullable=True
    )


class Dataset(Base, TimestampMixin):
    __tablename__ = "datasets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), unique=True)
    description: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    filename: Mapped[str] = mapped_column(String(255))
    file_path: Mapped[str] = mapped_column(String(500))
    vocabulary_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    document_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    sample_count: Mapped[int] = mapped_column(Integer, default=0)
    total_size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    curation_version: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(20), default="empty")
