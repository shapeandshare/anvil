"""Pydantic config model for ``TrainingRunService``.

Provides a HTTP-free config model matching ``TrainConfig`` from the API
layer, so ``TrainingRunService`` can be used from both the route handler
and the teaching loop without importing FastAPI types.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class TrainingRunConfig(BaseModel):
    """Training configuration for ``TrainingRunService.start_training_run``.

    Mirrors ``TrainConfig`` from the API layer but with no FastAPI
    dependency.  Business-logic constraints (divisibility, even head_dim)
    are enforced by the service's validation methods.

    Parameters
    ----------
    n_embd : int
        Embedding dimension. Default ``16``. Range ``[4, 4096]``.
    n_layer : int
        Number of transformer layers. Default ``1``. Range ``[1, 128]``.
    n_head : int
        Number of attention heads. Default ``4``. Range ``[1, 64]``.
    block_size : int
        Context window size. Default ``16``. Range ``[8, 4096]``.
    num_steps : int
        Training iterations. Default ``1000``. Range ``[1, 1000000]``.
    learning_rate : float
        Adam learning rate. Default ``0.01``. Range ``(0, 1.0]``.
    beta1 : float
        Adam beta1. Default ``0.85``.
    beta2 : float
        Adam beta2. Default ``0.99``.
    temperature : float
        Sampling temperature. Default ``0.5``. Range ``[0, 2.0]``.
    compute_backend : str | None
        Compute backend identifier. Default ``"auto"``.
    dataset_id : int | None
        Optional dataset ID for training data.
    corpus_id : int | None
        Optional corpus ID for training data.
    content_version_id : int | None
        Optional content version ID for reproducibility.
    device : str | None
        Optional device override (e.g. ``"cpu"``, ``"cuda:0"``, ``"mps"``).
    base_model_ref : int | None
        Optional experiment ID for warm-start.
    method : str
        Training method. ``"full"`` (default), ``"lora"``, or ``"qlora"``.
    lora_rank : int | None
        LoRA rank ``r``. Required when method is LoRA/QLoRA.
    lora_alpha : float | None
        LoRA scaling alpha. Required when method is LoRA/QLoRA.
    lora_target_modules : list[str] | None
        Target module names for LoRA.
    lora_dropout : float | None
        LoRA dropout rate. Range ``[0, 1]``.
    lora_bias : str | None
        LoRA bias setting: ``"none"``, ``"all"``, or ``"lora_only"``.
    """

    model_config = ConfigDict(extra="forbid")

    n_embd: int = Field(default=16, ge=4, le=4096)
    n_layer: int = Field(default=1, ge=1, le=128)
    n_head: int = Field(default=4, ge=1, le=64)
    block_size: int = Field(default=16, ge=8, le=4096)
    num_steps: int = Field(default=1000, ge=1, le=1_000_000)
    learning_rate: float = Field(default=0.01, gt=0, le=1.0)
    beta1: float = Field(default=0.85)
    beta2: float = Field(default=0.99)
    temperature: float = Field(default=0.5, ge=0, le=2.0)
    compute_backend: str | None = Field(default="auto")
    dataset_id: int | None = None
    corpus_id: int | None = None
    content_version_id: int | None = None
    device: str | None = None
    base_model_ref: int | None = None

    method: str = Field(default="full")
    lora_rank: int | None = Field(default=None, ge=1, le=1024)
    lora_alpha: float | None = Field(default=None, gt=0)
    lora_target_modules: list[str] | None = None
    lora_dropout: float | None = Field(default=None, ge=0, le=1)
    lora_bias: str | None = None
