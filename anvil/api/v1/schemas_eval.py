# Copyright © 2026 Josh Burt
# one-class:allow — intentional domain grouping of tightly coupled eval schemas
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Request body models for evaluation API endpoints.

Pure Pydantic ``BaseModel`` subclasses used for perplexity evaluation,
evaluation dataset creation, record management, and fine-tuned model
comparison evaluation (spec 054).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class EvalPerplexityBody(BaseModel):
    """Request body for computing perplexity on a text.

    Parameters
    ----------
    model_id : int
        Identifier of the model.
    version : int
        Version of the model.
    text : str
        Input text to evaluate. Must be non-empty.
    """

    model_config = ConfigDict(extra="forbid")

    model_id: int
    version: int
    text: str = Field(min_length=1)


class CreateEvalDatasetBody(BaseModel):
    """Request body for creating a new evaluation dataset.

    Parameters
    ----------
    name : str
        The dataset name. Must be 1-255 characters.
    tags : dict | None, optional
        Optional metadata tags. Defaults to ``None``.
    """

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=255)
    tags: dict[str, Any] | None = None


class AppendRecordsBody(BaseModel):
    """Request body for appending records to an evaluation dataset.

    Parameters
    ----------
    records : list
        List of evaluation records to append.
    """

    model_config = ConfigDict(extra="forbid")

    records: list[Any]


# ------------------------------------------------------------------
# Fine-tuned model evaluation schemas (spec 054)
# ------------------------------------------------------------------


class EvalFineTunedBody(BaseModel):
    """Request body for triggering a fine-tuned model evaluation.

    Parameters
    ----------
    model_id : int
        ``ExternalModel.id`` of the fine-tuned model.
    base_model_id : int
        ``ExternalModel.id`` of the base model.
    adapter_id : str | None, optional
        ``LoRAAdapter.adapter_id`` for adapter-model evaluation.
    eval_dataset_name : str | None, optional
        Name of an existing MLflow eval-dataset. If ``None``, the system
        attempts to auto-derive a held-out split.
    """

    model_config = ConfigDict(extra="forbid")

    model_id: int
    base_model_id: int
    adapter_id: str | None = None
    eval_dataset_name: str | None = None


class MetricDeltaResponse(BaseModel):
    """Serialised ``MetricDelta`` for API responses.

    Parameters
    ----------
    metric_name : str
        Metric name, e.g. ``"eval_loss"``, ``"perplexity"``.
    fine_tuned_value : float
        Metric value for the fine-tuned model.
    base_value : float
        Metric value for the base model.
    delta : float
        ``fine_tuned_value - base_value``.
    comparable : bool, optional
        Whether metrics are directly comparable. Defaults to ``True``.
    """

    metric_name: str
    fine_tuned_value: float
    base_value: float
    delta: float
    comparable: bool = True


class EvalSampleResponse(BaseModel):
    """Serialised ``EvalSample`` for API responses.

    Parameters
    ----------
    prompt_index : int
        Positional index in the prompt set.
    input : str
        The prompt text.
    base_output : str | None, optional
        Base model's generated output. Defaults to ``None``.
    fine_tuned_output : str | None, optional
        Fine-tuned model's generated output. Defaults to ``None``.
    base_loss : float | None, optional
        Per-sample loss for the base model. Defaults to ``None``.
    fine_tuned_loss : float | None, optional
        Per-sample loss for the fine-tuned model. Defaults to ``None``.
    """

    prompt_index: int
    input: str
    base_output: str | None = None
    fine_tuned_output: str | None = None
    base_loss: float | None = None
    fine_tuned_loss: float | None = None


class EvaluationRunResponse(BaseModel):
    """Serialised ``EvaluationRun`` for API responses.

    Parameters
    ----------
    run_id : int
        Primary key.
    model_id : int
        FK to ``ExternalModel.id`` of the fine-tuned model.
    model_name : str
        Display name of the fine-tuned model.
    base_model_id : int
        FK to ``ExternalModel.id`` of the base model.
    base_model_name : str
        Display name of the base model.
    adapter_id : str | None, optional
        Adapter ID, if applicable. Defaults to ``None``.
    tokenizer_family : str
        Tokenizer family of the fine-tuned model.
    base_tokenizer_family : str | None, optional
        Tokenizer family of the base model. Defaults to ``None``.
    status : str
        Run status (``EvaluationRunStatus``).
    prompt_count : int
        Number of prompts evaluated.
    metrics : list[MetricDeltaResponse], optional
        Metric deltas. Defaults to ``[]``.
    created_at : datetime
        When the run was created.
    started_at : datetime | None, optional
        When evaluation started. Defaults to ``None``.
    finished_at : datetime | None, optional
        When evaluation completed. Defaults to ``None``.
    mlflow_run_id : str | None, optional
        Pointer to the MLflow run. Defaults to ``None``.
    """

    run_id: int
    model_id: int
    model_name: str
    base_model_id: int
    base_model_name: str
    adapter_id: str | None = None
    tokenizer_family: str
    base_tokenizer_family: str | None = None
    status: str
    prompt_count: int
    metrics: list[MetricDeltaResponse] = []
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    mlflow_run_id: str | None = None


class EvaluationRunListResponse(BaseModel):
    """Paginated list of evaluation runs.

    Parameters
    ----------
    runs : list[EvaluationRunResponse]
        The returned runs.
    total : int
        Total number of matching runs.
    limit : int
        Max results per page.
    offset : int
        Current result offset.
    """

    runs: list[EvaluationRunResponse]
    total: int
    limit: int
    offset: int
