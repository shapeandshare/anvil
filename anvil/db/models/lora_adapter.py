"""LoRAAdapter ORM entity for tracking LoRA fine-tuning results."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..base import Base
from ..timestamp_mixin import TimestampMixin


class LoRAAdapter(Base, TimestampMixin):
    """A single LoRA fine-tuning result: adapter weights trained on a base model.

    Each row represents one completed fine-tuning run that produced a LoRA
    adapter. The adapter_id is auto-generated from the training run ID and
    scoped to the base model (``external_model_id``).

    Attributes
    ----------
    id : int
        Primary key, auto-increment.
    external_model_id : int
        FK to ``external_models.id`` — the base model this adapter applies to.
    run_id : int
        The training run ID that produced this adapter.
    adapter_id : str
        Auto-generated human-readable ID within base model scope
        (e.g. ``"run_42"``).
    label : str | None
        Optional user-provided display label.
    method : str
        Fine-tuning method: ``"lora"`` or ``"qlora"``.
    storage_path : str
        Relative path to adapter directory within the store.
    lora_rank : int
        LoRA rank (r).
    lora_alpha : float
        LoRA scaling alpha.
    lora_target_modules : str | None
        JSON-encoded list of target module names (e.g. ``'["q_proj","v_proj"]'``).
    lora_dropout : float | None
        LoRA dropout rate.
    lora_bias : str | None
        Bias setting (``"none"``, ``"all"``, ``"lora_only"``).
    final_loss : float | None
        Final training loss.
    final_step : int | None
        Final training step.
    merged_at : datetime | None
        Timestamp of optional merge operation. ``None`` if not yet merged.
    created_at : datetime
        TimestampMixin: row creation time.
    updated_at : datetime
        TimestampMixin: row last-update time.
    """

    __tablename__ = "lora_adapters"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    external_model_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("external_models.id", ondelete="CASCADE"),
        nullable=False,
    )
    run_id: Mapped[int] = mapped_column(Integer, nullable=False)
    adapter_id: Mapped[str] = mapped_column(String(255), nullable=False)
    label: Mapped[str | None] = mapped_column(String(255), nullable=True)
    method: Mapped[str] = mapped_column(String(20), nullable=False)
    storage_path: Mapped[str] = mapped_column(String(512), nullable=False)
    lora_rank: Mapped[int] = mapped_column(Integer, nullable=False)
    lora_alpha: Mapped[float] = mapped_column(Float, nullable=False)
    lora_target_modules: Mapped[str | None] = mapped_column(Text, nullable=True)
    lora_dropout: Mapped[float | None] = mapped_column(Float, nullable=True)
    lora_bias: Mapped[str | None] = mapped_column(String(20), nullable=True)
    final_loss: Mapped[float | None] = mapped_column(Float, nullable=True)
    final_step: Mapped[int | None] = mapped_column(Integer, nullable=True)
    merged_at: Mapped[datetime | None] = mapped_column(Integer, nullable=True)
