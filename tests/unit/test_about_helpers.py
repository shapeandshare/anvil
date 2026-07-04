"""Unit tests for the shared environment snapshot helper.

Tests the ``_get_git_commit_hash`` helper and ``_collect_environment_snapshot``
function that power the about page and health/detailed endpoint.
"""

from __future__ import annotations

from unittest.mock import patch


def test_get_git_commit_hash_returns_string() -> None:
    """Test that ``_get_git_commit_hash`` returns a non-empty string.

    This test verifies the basic happy path — the function must
    always return a string, never ``None`` or an empty string.
    """
    from anvil.api.v1._environment import _get_git_commit_hash

    result = _get_git_commit_hash()
    assert isinstance(result, str)
    assert len(result) > 0


def test_get_git_commit_hash_returns_unknown_on_failure() -> None:
    """Test that ``_get_git_commit_hash`` returns ``"unknown"`` when git
    fails.

    Simulates the scenario where the ``.git`` directory is not
    available (e.g. pip-installed wheel) by monkeypatching
    ``subprocess.run`` to raise ``OSError``.
    """
    with patch("anvil.api.v1._environment.subprocess.run") as mock_run:
        mock_run.side_effect = OSError("git not found")
        from anvil.api.v1._environment import _get_git_commit_hash

        result = _get_git_commit_hash()
        assert result == "unknown"
