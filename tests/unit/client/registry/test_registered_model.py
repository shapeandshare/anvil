# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Tests for the RegisteredModel DTO — construction, defaults, and
serialization.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from anvil.client.registry.registered_model import RegisteredModel


class TestRegisteredModelConstruction:
    """RegisteredModel construction with various parameter combinations."""

    def test_minimal_construction(self) -> None:
        rm = RegisteredModel(model_id="m-1", name="my-model")
        assert rm.model_id == "m-1"
        assert rm.name == "my-model"
        assert rm.versions == []
        assert rm.created_at is None

    def test_full_construction(self) -> None:
        rm = RegisteredModel(
            model_id="m-42",
            name="full-model",
            versions=["v1", "v2"],
            created_at="2026-06-01T12:00:00Z",
        )
        assert rm.model_id == "m-42"
        assert rm.name == "full-model"
        assert rm.versions == ["v1", "v2"]
        assert rm.created_at == "2026-06-01T12:00:00Z"

    def test_construction_with_single_version(self) -> None:
        rm = RegisteredModel(model_id="m-3", name="single-ver", versions=["v1"])
        assert rm.versions == ["v1"]


class TestRegisteredModelDefaults:
    """Default values for optional fields."""

    def test_versions_defaults_to_empty_list(self) -> None:
        assert RegisteredModel(model_id="x", name="x").versions == []

    def test_created_at_defaults_to_none(self) -> None:
        assert RegisteredModel(model_id="x", name="x").created_at is None


class TestRegisteredModelValidation:
    """Pydantic validation constraints."""

    def test_model_id_required(self) -> None:
        with pytest.raises(ValidationError):
            RegisteredModel(name="x")  # type: ignore[call-arg]

    def test_name_required(self) -> None:
        with pytest.raises(ValidationError):
            RegisteredModel(model_id="x")  # type: ignore[call-arg]

    def test_versions_must_be_list(self) -> None:
        with pytest.raises(ValidationError):
            RegisteredModel(model_id="x", name="x", versions="not-a-list")  # type: ignore[arg-type]


class TestRegisteredModelSerialization:
    """Round-trip JSON serialization / deserialization."""

    def test_serialize_to_dict(self) -> None:
        rm = RegisteredModel(model_id="m-1", name="test", versions=["v1"])
        data = rm.model_dump()
        assert data["model_id"] == "m-1"
        assert data["name"] == "test"
        assert data["versions"] == ["v1"]
        assert data["created_at"] is None

    def test_round_trip_json(self) -> None:
        rm = RegisteredModel(
            model_id="m-99",
            name="roundtrip",
            versions=["v1", "v2"],
            created_at="2026-06-01T00:00:00Z",
        )
        json_str = rm.model_dump_json()
        restored = RegisteredModel.model_validate_json(json_str)
        assert restored.model_id == "m-99"
        assert restored.name == "roundtrip"
        assert restored.versions == ["v1", "v2"]
        assert restored.created_at == "2026-06-01T00:00:00Z"

    def test_deserialize_from_dict(self) -> None:
        raw = {"model_id": "m-7", "name": "from-dict", "versions": ["v0"]}
        rm = RegisteredModel.model_validate(raw)
        assert rm.model_id == "m-7"
        assert rm.name == "from-dict"
        assert rm.versions == ["v0"]