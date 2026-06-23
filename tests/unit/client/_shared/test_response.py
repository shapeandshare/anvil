# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Tests for the generic Response[T] envelope unwrapper."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from anvil.client._shared.response import Response


class _DummyData(BaseModel):
    """Minimal test DTO for Response[T] generic validation."""

    model_config = ConfigDict(extra="forbid")

    name: str
    value: int


class TestResponse:
    """Envelope unwrap and validation behavior."""

    def test_success_response_unwraps_data(self) -> None:
        raw = {"data": {"name": "test", "value": 42}, "error": None}
        parsed = Response[_DummyData].model_validate(raw)
        assert parsed.error is None
        assert parsed.data is not None
        assert parsed.data.name == "test"
        assert parsed.data.value == 42

    def test_error_response_has_null_data(self) -> None:
        raw = {"data": None, "error": "something went wrong"}
        parsed = Response[_DummyData].model_validate(raw)
        assert parsed.error == "something went wrong"
        assert parsed.data is None

    def test_success_envelope_null_error_and_data(self) -> None:
        raw = {"data": {"name": "x", "value": 1}, "error": None}
        parsed = Response[_DummyData].model_validate(raw)
        assert parsed.data is not None

    def test_extra_fields_forbidden(self) -> None:
        raw = {"data": {"name": "x", "value": 1}, "error": None, "extra": True}
        import json

        import pytest
        from pydantic import ValidationError

        raw_str = json.dumps(raw)
        with pytest.raises(ValidationError):
            Response[_DummyData].model_validate_json(raw_str)

    def test_response_generic_preserves_type(self) -> None:
        raw = {"data": {"name": "hello", "value": 99}, "error": None}
        parsed = Response[_DummyData].model_validate(raw)
        assert isinstance(parsed.data, _DummyData)
