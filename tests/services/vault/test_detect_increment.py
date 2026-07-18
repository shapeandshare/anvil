# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Tests for :mod:`anvil.services.vault.detect_increment` — version
increment detection.
"""

from __future__ import annotations

from collections.abc import Generator
from unittest.mock import patch

import pytest

from anvil.services.vault.detect_increment import _merge_message, main


class TestMergeMessage:
    """Tests for ``_merge_message``."""

    def test_returns_stripped_message(self) -> None:
        """Verify ``_merge_message`` calls ``git log`` and strips the result."""
        with patch("anvil.services.vault.detect_increment.subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = "feat: add widget\n"
            msg = _merge_message()
            assert msg == "feat: add widget"

    def test_empty_on_git_failure(self) -> None:
        with patch("anvil.services.vault.detect_increment.subprocess.run") as mock_run:
            mock_run.return_value.returncode = 1
            mock_run.return_value.stdout = ""
            msg = _merge_message()
            assert msg == ""


class TestMainConventionalCommit:
    """Tests for ``main()`` with conventional commit messages."""

    @pytest.fixture(autouse=True)
    def _setup_env(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> Generator[None, None, None]:
        monkeypatch.delenv("GITHUB_EVENT_NAME", raising=False)
        yield

    def test_feat_returns_auto(self, capsys: pytest.CaptureFixture[str]) -> None:
        """A 'feat' merge message classifies as AUTO."""
        with (
            patch(
                "anvil.services.vault.detect_increment._merge_message",
                return_value="feat: add new training dashboard\n",
            ),
            patch(
                "anvil.services.vault.detect_increment._read_version",
                return_value="0.5.0",
            ),
            patch(
                "anvil.services.vault.detect_increment._parent_version",
                return_value="0.5.0",
            ),
        ):
            main()
        captured = capsys.readouterr()
        assert "increment=AUTO" in captured.out
        assert "version_changed=true" in captured.out

    def test_fix_returns_auto(self, capsys: pytest.CaptureFixture[str]) -> None:
        """A 'fix' merge message classifies as AUTO."""
        with (
            patch(
                "anvil.services.vault.detect_increment._merge_message",
                return_value="fix: resolve model loading crash\n",
            ),
            patch(
                "anvil.services.vault.detect_increment._read_version",
                return_value="0.5.0",
            ),
            patch(
                "anvil.services.vault.detect_increment._parent_version",
                return_value="0.5.0",
            ),
        ):
            main()
        captured = capsys.readouterr()
        assert "increment=AUTO" in captured.out
        assert "version_changed=true" in captured.out

    def test_breaking_returns_auto(self, capsys: pytest.CaptureFixture[str]) -> None:
        """A BREAKING CHANGE merge message classifies as AUTO."""
        with (
            patch(
                "anvil.services.vault.detect_increment._merge_message",
                return_value="feat: rewrite engine\n\nBREAKING CHANGE: new API\n",
            ),
            patch(
                "anvil.services.vault.detect_increment._read_version",
                return_value="0.5.0",
            ),
            patch(
                "anvil.services.vault.detect_increment._parent_version",
                return_value="0.5.0",
            ),
        ):
            main()
        captured = capsys.readouterr()
        assert "increment=AUTO" in captured.out
        assert "version_changed=true" in captured.out

    def test_chore_returns_auto(self, capsys: pytest.CaptureFixture[str]) -> None:
        """A 'chore' merge message classifies as AUTO."""
        with (
            patch(
                "anvil.services.vault.detect_increment._merge_message",
                return_value="chore: bump deps\n",
            ),
            patch(
                "anvil.services.vault.detect_increment._read_version",
                return_value="0.5.0",
            ),
            patch(
                "anvil.services.vault.detect_increment._parent_version",
                return_value="0.5.0",
            ),
        ):
            main()
        captured = capsys.readouterr()
        assert "increment=AUTO" in captured.out
        assert "version_changed=true" in captured.out


class TestMainEnvOverrides:
    """Tests for ``main()`` with environment variable overrides."""

    def test_workflow_dispatch_returns_patch(
        self,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("GITHUB_EVENT_NAME", "workflow_dispatch")
        with (
            patch(
                "anvil.services.vault.detect_increment._read_version",
                return_value="0.5.0",
            ),
            patch(
                "anvil.services.vault.detect_increment._parent_version",
                return_value="0.5.0",
            ),
        ):
            main()
        captured = capsys.readouterr()
        assert "increment=PATCH" in captured.out
        assert "version_changed=true" in captured.out

    def test_version_changed_skips_classification(
        self,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.delenv("GITHUB_EVENT_NAME", raising=False)
        with (
            patch(
                "anvil.services.vault.detect_increment._read_version",
                return_value="0.6.0",
            ),
            patch(
                "anvil.services.vault.detect_increment._parent_version",
                return_value="0.5.0",
            ),
        ):
            main()
        captured = capsys.readouterr()
        assert "increment=SKIP" in captured.out
        assert "version_changed=true" in captured.out

    def test_invalid_version_unknown(self, capsys: pytest.CaptureFixture[str]) -> None:
        with (
            patch(
                "anvil.services.vault.detect_increment._read_version",
                return_value=None,
            ),
            patch(
                "anvil.services.vault.detect_increment._parent_version",
                return_value=None,
            ),
            patch(
                "anvil.services.vault.detect_increment._merge_message",
                return_value="",
            ),
        ):
            main()
        captured = capsys.readouterr()
        assert "version=unknown" in captured.out
