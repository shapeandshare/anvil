# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Tests for TrainingConfig DTO — construction, defaults, validation, and serialization."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from anvil.client.training.training_config import TrainingConfig


class TestTrainingConfigConstruction:
    """TrainingConfig construction with various parameter combinations."""

    def test_minimal_construction(self) -> None:
        config = TrainingConfig()
        assert config.n_embd == 16
        assert config.n_layer == 1
        assert config.n_head == 4
        assert config.block_size == 16
        assert config.num_steps == 1000
        assert config.learning_rate == 0.01
        assert config.beta1 == 0.85
        assert config.beta2 == 0.99
        assert config.temperature == 0.5
        assert config.compute_backend == "auto"
        assert config.dataset_id is None
        assert config.corpus_id is None
        assert config.content_version_id is None
        assert config.device is None

    def test_full_construction(self) -> None:
        config = TrainingConfig(
            n_embd=64,
            n_layer=4,
            n_head=8,
            block_size=128,
            num_steps=5000,
            learning_rate=0.001,
            beta1=0.9,
            beta2=0.999,
            temperature=0.8,
            compute_backend="local-torch",
            dataset_id=1,
            corpus_id=2,
            content_version_id="v3",
            device="cuda:0",
        )
        assert config.n_embd == 64
        assert config.n_layer == 4
        assert config.n_head == 8
        assert config.block_size == 128
        assert config.num_steps == 5000
        assert config.learning_rate == 0.001
        assert config.beta1 == 0.9
        assert config.beta2 == 0.999
        assert config.temperature == 0.8
        assert config.compute_backend == "local-torch"
        assert config.dataset_id == 1
        assert config.corpus_id == 2
        assert config.content_version_id == "v3"
        assert config.device == "cuda:0"


class TestTrainingConfigValidation:
    """Pydantic validation constraints."""

    def test_n_head_must_divide_n_embd(self) -> None:
        with pytest.raises(ValueError, match="n_head"):
            TrainingConfig(n_embd=16, n_head=3)

    def test_valid_n_head_division(self) -> None:
        config = TrainingConfig(n_embd=32, n_head=8)
        assert config.n_head == 8
        assert config.n_embd == 32

    def test_equal_n_head_and_n_embd(self) -> None:
        config = TrainingConfig(n_embd=16, n_head=16)
        assert config.n_embd % config.n_head == 0


class TestTrainingConfigSerialization:
    """Round-trip serialization."""

    def test_serialize_to_dict(self) -> None:
        config = TrainingConfig(n_embd=32, n_head=8, num_steps=2000)
        data = config.model_dump()
        assert data["n_embd"] == 32
        assert data["n_head"] == 8
        assert data["num_steps"] == 2000

    def test_round_trip_json(self) -> None:
        config = TrainingConfig(n_embd=64, n_head=8, num_steps=3000)
        json_str = config.model_dump_json()
        restored = TrainingConfig.model_validate_json(json_str)
        assert restored.n_embd == 64
        assert restored.n_head == 8
        assert restored.num_steps == 3000
