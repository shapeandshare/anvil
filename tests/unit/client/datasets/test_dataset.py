# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Tests for the Dataset DTO — construction, defaults, and serialization."""

from __future__ import annotations

from datetime import datetime, timezone, UTC

import pytest
from pydantic import ValidationError

from anvil.client.datasets.dataset import Dataset


class TestDatasetConstruction:
    """Dataset construction with various parameter combinations."""

    def test_minimal_construction(self) -> None:
        ds = Dataset(id=1, name="my-dataset")
        assert ds.id == 1
        assert ds.name == "my-dataset"
        assert ds.description is None
        assert ds.sample_count == 0
        assert ds.created_at is None
        assert ds.updated_at is None

    def test_full_construction(self) -> None:
        dt = datetime(2026, 6, 1, 12, 0, 0, tzinfo=UTC)
        ds = Dataset(
            id=42,
            name="full-dataset",
            description="A test dataset",
            sample_count=100,
            created_at=dt,
            updated_at=dt,
        )
        assert ds.id == 42
        assert ds.name == "full-dataset"
        assert ds.description == "A test dataset"
        assert ds.sample_count == 100
        assert ds.created_at == dt
        assert ds.updated_at == dt


class TestDatasetDefaults:
    """Default values for optional fields."""

    def test_description_defaults_to_none(self) -> None:
        assert Dataset(id=1, name="x").description is None

    def test_sample_count_defaults_to_zero(self) -> None:
        assert Dataset(id=1, name="x").sample_count == 0

    def test_created_at_defaults_to_none(self) -> None:
        assert Dataset(id=1, name="x").created_at is None

    def test_updated_at_defaults_to_none(self) -> None:
        assert Dataset(id=1, name="x").updated_at is None


class TestDatasetValidation:
    """Pydantic validation constraints."""

    def test_id_required(self) -> None:
        with pytest.raises(ValidationError):
            Dataset(name="x")  # type: ignore[call-arg]

    def test_name_required(self) -> None:
        with pytest.raises(ValidationError):
            Dataset(id=1)  # type: ignore[call-arg]

    def test_id_must_be_int(self) -> None:
        with pytest.raises(ValidationError):
            Dataset(id="not-an-int", name="x")  # type: ignore[arg-type]


class TestDatasetSerialization:
    """Round-trip JSON serialization / deserialization."""

    def test_serialize_to_dict(self) -> None:
        ds = Dataset(id=1, name="test", sample_count=5)
        data = ds.model_dump()
        assert data["id"] == 1
        assert data["name"] == "test"
        assert data["sample_count"] == 5
        assert data["description"] is None
        assert data["created_at"] is None
        assert data["updated_at"] is None

    def test_round_trip_json(self) -> None:
        ds = Dataset(id=99, name="roundtrip", sample_count=42)
        json_str = ds.model_dump_json()
        restored = Dataset.model_validate_json(json_str)
        assert restored.id == 99
        assert restored.name == "roundtrip"
        assert restored.sample_count == 42

    def test_deserialize_from_dict(self) -> None:
        raw = {"id": 7, "name": "from-dict", "sample_count": 10}
        ds = Dataset.model_validate(raw)
        assert ds.id == 7
        assert ds.name == "from-dict"
        assert ds.sample_count == 10
