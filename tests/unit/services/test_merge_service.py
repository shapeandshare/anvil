"""Tests for merge_service utilities — path sanitisation."""

from __future__ import annotations

import pytest

from anvil.services.training.merge_service import _safe_path_component


class TestSafePathComponent:
    """Tests for _safe_path_component — path sanitisation."""

    def test_allows_alphanumeric(self) -> None:
        assert _safe_path_component("hello123") == "hello123"

    def test_allows_dot_dash_underscore(self) -> None:
        assert _safe_path_component("my.adapter-v1_final") == "my.adapter-v1_final"

    def test_replaces_special_chars_with_underscore(self) -> None:
        result = _safe_path_component("my adapter/name@#$%")
        assert "/" not in result
        assert "@" not in result
        assert result == "my_adapter_name____"

    def test_strips_whitespace_to_underscore(self) -> None:
        assert _safe_path_component("hello world") == "hello_world"

    def test_truncates_to_default_max_len(self) -> None:
        long_name = "a" * 200
        result = _safe_path_component(long_name)
        assert len(result) == 128

    def test_truncates_to_custom_max_len(self) -> None:
        result = _safe_path_component("hello world", max_len=5)
        assert result == "hello"

    def test_raises_on_empty_result(self) -> None:
        with pytest.raises(ValueError, match="empty after sanitisation"):
            _safe_path_component("")

    def test_special_chars_become_underscores(self) -> None:
        result = _safe_path_component("!!!@@@###")
        assert "!" not in result
        assert "@" not in result
