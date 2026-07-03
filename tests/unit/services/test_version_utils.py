# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Tests for version_utils — version string extraction and increment classification."""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

import pytest

from anvil.services._shared.version_utils import (
    classify_increment,
    parent_version,
    read_version,
)


class TestReadVersion:
    """Tests for read_version() — parsing pyproject.toml."""

    def test_reads_version_from_toml(self):
        """Happy path: finds version = "X.Y.Z" in a pyproject.toml."""
        with tempfile.TemporaryDirectory() as tmp:
            toml = Path(tmp) / "pyproject.toml"
            toml.write_text('[project]\nname = "anvil"\nversion = "0.5.0"\n')
            result = read_version(str(toml))
            assert result == "0.5.0"

    def test_returns_none_when_version_missing(self):
        """No version field → None."""
        with tempfile.TemporaryDirectory() as tmp:
            toml = Path(tmp) / "pyproject.toml"
            toml.write_text('[project]\nname = "anvil"\n')
            result = read_version(str(toml))
            assert result is None

    def test_returns_none_when_file_not_found(self):
        """Missing file → None."""
        result = read_version("/nonexistent/path/pyproject.toml")
        assert result is None

    def test_skips_commented_versions(self):
        """Lines matching version but commented should be skipped."""
        with tempfile.TemporaryDirectory() as tmp:
            toml = Path(tmp) / "pyproject.toml"
            toml.write_text('# version = "0.1.0"\nversion = "1.0.0"\n')
            result = read_version(str(toml))
            assert result == "1.0.0"

    def test_ignores_non_matching_lines(self):
        """Lines without version = are skipped gracefully."""
        with tempfile.TemporaryDirectory() as tmp:
            toml = Path(tmp) / "pyproject.toml"
            toml.write_text('requires-python = ">=3.11"\n')
            result = read_version(str(toml))
            assert result is None


class TestParentVersion:
    """Tests for parent_version() — reading version from parent git commit."""

    def test_returns_version_when_parent_exists(self, monkeypatch):
        """HEAD^ commit has pyproject.toml with version."""

        def _fake_run(cmd, **kwargs):  # type: ignore[no-untyped-def]
            class _Result:
                returncode = 0
                stdout = '[project]\nversion = "0.4.0"\n'
                stderr = ""

            return _Result()

        monkeypatch.setattr(subprocess, "run", _fake_run)
        result = parent_version()
        assert result == "0.4.0"

    def test_returns_none_when_no_parent(self, monkeypatch):
        """HEAD^ does not exist (first commit) → None."""

        def _fake_run(cmd, **kwargs):  # type: ignore[no-untyped-def]
            class _Result:
                returncode = 128
                stdout = ""
                stderr = "fatal: ambiguous argument 'HEAD^': unknown revision"

            return _Result()

        monkeypatch.setattr(subprocess, "run", _fake_run)
        result = parent_version()
        assert result is None

    def test_returns_none_when_version_missing_in_parent(self, monkeypatch):
        """Parent exists but no version field → None."""

        def _fake_run(cmd, **kwargs):  # type: ignore[no-untyped-def]
            class _Result:
                returncode = 0
                stdout = '[project]\nname = "anvil"\n'
                stderr = ""

            return _Result()

        monkeypatch.setattr(subprocess, "run", _fake_run)
        result = parent_version()
        assert result is None


class TestClassifyIncrement:
    """Tests for classify_increment() — conventional-commit increment detection."""

    def test_breaking_change_is_major(self):
        """BREAKING CHANGE in message → MAJOR."""
        assert classify_increment("feat!: BREAKING CHANGE the API") == "MAJOR"
        assert classify_increment("fix: breaking change in behavior") == "MAJOR"
        assert classify_increment("BREAKING CHANGE: drop support") == "MAJOR"

    def test_feat_is_minor(self):
        """feat: prefix → MINOR."""
        assert classify_increment("feat: add new endpoint") == "MINOR"
        assert classify_increment("feat(core): add RoPE support") == "MINOR"

    def test_fix_is_patch(self):
        """fix: prefix → PATCH."""
        assert classify_increment("fix: correct off-by-one error") == "PATCH"
        assert classify_increment("fix(api): handle null response") == "PATCH"

    def test_non_feature_types_are_none(self):
        """perf|refactor|chore|docs|ci|test|style|build → NONE."""
        assert classify_increment("perf: optimize attention") == "NONE"
        assert classify_increment("refactor: extract helper") == "NONE"
        assert classify_increment("chore: bump deps") == "NONE"
        assert classify_increment("docs: add docstring") == "NONE"
        assert classify_increment("ci: fix workflow") == "NONE"
        assert classify_increment("test: add coverage") == "NONE"
        assert classify_increment("style: format code") == "NONE"
        assert classify_increment("build: update config") == "NONE"

    def test_unknown_prefix_is_none(self):
        """Unrecognised prefix → NONE."""
        assert classify_increment("random: something") == "NONE"
        assert classify_increment("nothing special") == "NONE"
        assert classify_increment("") == "NONE"

    def test_feat_with_breaking_is_major_not_minor(self):
        """BREAKING CHANGE text in body takes priority over feat prefix."""
        assert (
            classify_increment("feat: add thing\n\nBREAKING CHANGE: incompatible")
            == "MAJOR"
        )
        assert classify_increment("refactor: BREAKING CHANGE the API") == "MAJOR"

    def test_feat_with_exclamation_not_major(self):
        """Feat! marker alone does not trigger MAJOR (only 'BREAKING CHANGE' text does)."""
        assert classify_increment("feat!: add risky thing") == "MINOR"
