# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""EvaluationRun, MetricDelta, and EvalSample ORM entities.

Three tightly coupled model classes grouped in one file to avoid circular
imports between the bidirectional FK relationships.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..base import Base
from ..timestamp_mixin import TimestampMixin


class EvaluationRun(Base, TimestampMixin):
    """A single fine-tuned model evaluation: comparing a model against its base.

    Records the prompts, per-prompt sample outputs, metrics, metric deltas,
    and an ``mlflow_run_id`` pointer to the MLflow run holding the full
    config/hardware/environment provenance.

    Attributes
    ----------
    id : int
        Primary key, auto-increment.
    external_model_id : int
        FK to ``external_models.id`` — the fine-tuned model under evaluation.
    base_external_model_id : int | None
        FK to ``external_models.id`` — the base model compared against, or
        ``None`` for from-scratch models.
    adapter_id : str | None
        Scoped adapter ID for adapter-model evaluations, e.g. ``"run_42"``.
    tokenizer_family : str
        Tokenizer family of the fine-tuned model (043 dispatch).
    base_tokenizer_family : str | None
        Tokenizer family of the base model, for cross-tokenizer comparison.
    eval_dataset_name : str | None
        Name of the MLflow eval-dataset used, or ``None`` if held-out split used.
    status : str
        Run status — ``EvaluationRunStatus`` value.
    mlflow_run_id : str | None
        Pointer to the MLflow run for config/environment/hardware provenance.
    prompt_count : int
        Number of prompts evaluated.
    meta : str | None
        JSON-encoded metadata.
    started_at : datetime | None
        When evaluation started.
    finished_at : datetime | None
        When evaluation completed or failed.
    error_message : str | None
        Error detail if ``status == "failed"``.
    """

    __tablename__ = "evaluation_runs"
    __table_args__ = (Index("ix_evaluation_runs_created_at", "created_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    external_model_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("external_models.id"), nullable=False, index=True
    )
    base_external_model_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("external_models.id"), nullable=True, index=True
    )
    adapter_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    tokenizer_family: Mapped[str] = mapped_column(String(100), nullable=False)
    base_tokenizer_family: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )
    eval_dataset_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending", index=True
    )
    mlflow_run_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    prompt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    meta: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships (not essential for v1 but useful for FK navigation)
    metric_deltas = relationship(
        "MetricDelta", back_populates="evaluation_run", cascade="all, delete-orphan"
    )
    samples = relationship(
        "EvalSample", back_populates="evaluation_run", cascade="all, delete-orphan"
    )


class MetricDelta(Base, TimestampMixin):
    """A recorded base→fine-tuned metric comparison within an evaluation run.

    Attributes
    ----------
    id : int
        Primary key, auto-increment.
    evaluation_run_id : int
        FK to ``evaluation_runs.id``, CASCADE on delete.
    metric_name : str
        Metric name, e.g. ``"eval_loss"``, ``"perplexity"``.
    fine_tuned_value : float
        Metric value for the fine-tuned model.
    base_value : float
        Metric value for the base model.
    delta : float
        ``fine_tuned_value - base_value`` (pre-computed for queryability).
    comparable : bool
        Whether the metrics are directly comparable. ``False`` when tokenizer
        families differ.
    """

    __tablename__ = "metric_deltas"
    __table_args__ = (
        UniqueConstraint(
            "evaluation_run_id", "metric_name", name="uq_metric_delta_per_run"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    evaluation_run_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("evaluation_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    metric_name: Mapped[str] = mapped_column(String(100), nullable=False)
    fine_tuned_value: Mapped[float] = mapped_column(Float, nullable=False)
    base_value: Mapped[float] = mapped_column(Float, nullable=False)
    delta: Mapped[float] = mapped_column(Float, nullable=False)
    comparable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    evaluation_run = relationship("EvaluationRun", back_populates="metric_deltas")


class EvalSample(Base, TimestampMixin):
    """A single per-prompt sample output within an evaluation run.

    Records the prompt input, both models' generated outputs, and per-sample
    losses for side-by-side display.

    Attributes
    ----------
    id : int
        Primary key, auto-increment.
    evaluation_run_id : int
        FK to ``evaluation_runs.id``, CASCADE on delete.
    prompt_index : int
        Positional index in the prompt set.
    input : str
        The prompt text.
    base_output : str | None
        Base model's generated output, or ``None`` if generation failed.
    fine_tuned_output : str | None
        Fine-tuned model's generated output, or ``None`` if generation failed.
    base_loss : float | None
        Per-sample loss for the base model, or ``None`` if not computed.
    fine_tuned_loss : float | None
        Per-sample loss for the fine-tuned model, or ``None`` if not computed.
    """

    __tablename__ = "eval_samples"
    __table_args__ = (
        UniqueConstraint("evaluation_run_id", "prompt_index", name="uq_sample_per_run"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    evaluation_run_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("evaluation_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    prompt_index: Mapped[int] = mapped_column(Integer, nullable=False)
    input: Mapped[str] = mapped_column(Text, nullable=False)
    base_output: Mapped[str | None] = mapped_column(Text, nullable=True)
    fine_tuned_output: Mapped[str | None] = mapped_column(Text, nullable=True)
    base_loss: Mapped[float | None] = mapped_column(Float, nullable=True)
    fine_tuned_loss: Mapped[float | None] = mapped_column(Float, nullable=True)

    evaluation_run = relationship("EvaluationRun", back_populates="samples")
