# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Training configuration model.

``TrainingConfig`` encapsulates every hyperparameter and data-source
reference needed to start a training run on the anvil server.
"""

from __future__ import annotations

from pydantic import BaseModel, model_validator


class TrainingConfig(BaseModel):
    """Hyperparameters and data-source references for a training run.

    Parameters
    ----------
    n_embd : int
        Embedding dimension. Defaults to ``16``.
    n_layer : int
        Number of transformer layers. Defaults to ``1``.
    n_head : int
        Number of attention heads. Must divide ``n_embd``. Defaults to
        ``4``.
    block_size : int
        Context window size in tokens. Defaults to ``16``.
    num_steps : int
        Number of training iterations. Defaults to ``1000``.
    learning_rate : float
        Adam learning rate. Defaults to ``0.01``.
    beta1 : float
        Adam beta1. Defaults to ``0.85``.
    beta2 : float
        Adam beta2. Defaults to ``0.99``.
    temperature : float
        Sampling temperature for generation. Defaults to ``0.5``.
    compute_backend : str
        Compute backend identifier (``"auto"``, ``"local-stdlib"``,
        ``"local-torch"``, ``"modal"``). Defaults to ``"auto"``.
    dataset_id : int | None
        Primary key of an existing dataset to train on. Defaults to
        ``None``.
    corpus_id : int | None
        Primary key of a corpus to train on. Defaults to ``None``.
    content_version_id : str | None
        Specific content version identifier. Defaults to ``None``.
    device : str | None
        Device override (``"cpu"``, ``"cuda:0"``, ``"mps"``). Defaults
        to ``None`` (auto-detect).
    """

    n_embd: int = 16
    n_layer: int = 1
    n_head: int = 4
    block_size: int = 16
    num_steps: int = 1000
    learning_rate: float = 0.01
    beta1: float = 0.85
    beta2: float = 0.99
    temperature: float = 0.5
    compute_backend: str = "auto"
    dataset_id: int | None = None
    corpus_id: int | None = None
    content_version_id: str | None = None
    device: str | None = None

    @model_validator(mode="after")
    def validate_n_head_divisible(self) -> TrainingConfig:
        """Ensure ``n_head`` divides ``n_embd``.

        Returns
        -------
        TrainingConfig
            The validated instance.

        Raises
        ------
        ValueError
            If ``n_head`` does not divide ``n_embd`` evenly.
        """
        if self.n_embd % self.n_head != 0:
            raise ValueError(
                f"n_head={self.n_head} must divide n_embd={self.n_embd}",
            )
        return self
