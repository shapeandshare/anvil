# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""TrainingConfig ORM model for training run configurations.

This module defines the ``TrainingConfig`` model, which stores the
hyperparameters and settings for a training run. Configurations
include the transformer architecture parameters (layers, embedding
size, heads, block size), optimizer settings (learning rate, betas),
sampling temperature, GPU usage flag, and optional dataset or corpus
associations.
"""

from sqlalchemy import Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from ..base import Base
from ..timestamp_mixin import TimestampMixin


class TrainingConfig(Base, TimestampMixin):
    """A training run configuration (hyperparameters and settings).

    Maps to the ``training_configs`` table. Each row stores the
    complete set of hyperparameters for a training run, including
    transformer architecture parameters (``n_layer``, ``n_embd``,
    ``n_head``, ``block_size``), optimizer settings (``learning_rate``,
    ``beta1``, ``beta2``), sampling parameters (``temperature``),
    GPU usage flag, and optional foreign keys to a dataset or corpus.

    Mapped columns
    --------------
    id : int
        Primary key, auto-increment.
    name : str or None
        Optional human-readable name for this config (255 chars max).
    n_layer : int
        Number of transformer layers (default ``1``).
    n_embd : int
        Embedding dimension (default ``16``).
    n_head : int
        Number of attention heads (default ``4``).
    block_size : int
        Maximum sequence length / context window (default ``16``).
    num_steps : int
        Number of training steps (default ``1000``).
    learning_rate : float
        Adam learning rate (default ``0.01``).
    beta1 : float
        Adam beta1 coefficient (default ``0.85``).
    beta2 : float
        Adam beta2 coefficient (default ``0.99``).
    temperature : float
        Sampling temperature (default ``0.5``).
    dataset_id : int or None
        Foreign key to ``datasets.id``.
    corpus_id : int or None
        Foreign key to ``corpora.id``.
    """

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
    dataset_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("datasets.id"), nullable=True
    )
    corpus_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("corpora.id"), nullable=True
    )
