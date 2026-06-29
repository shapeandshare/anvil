"""Unit tests for anvil/services/vault/detect_increment.py.

Tests merge message detection and the main() entry point by
mocking subprocess and version_utils calls.
"""

from __future__ import annotations

import os
import sys
from unittest.mock import patch

import pytest

from anvil.services.vault.detect_increment import _merge_message, main


##############################################################################
# _merge_message
##############################################################################


@patch("anvil.services.vault.detect_increment.subprocess.run")
def test_merge_message_success(mock_run) -> None:
    """_merge_message returns stdout on success."""
    mock_run.return_value.returncode = 0
    mock_run.return_value.stdout = "feat: add widget\n\nDetails.\n"
    assert _merge_message() == "feat: add widget\n\nDetails."


@patch("anvil.services.vault.detect_increment.subprocess.run")
def test_merge_message_failure(mock_run) -> None:
    """_merge_message returns empty string on failure."""
    mock_run.return_value.returncode = 1
    mock_run.return_value.stdout = ""
    assert _merge_message() == ""


@patch("anvil.services.vault.detect_increment.subprocess.run")
def test_merge_message_empty_stdout(mock_run) -> None:
    """_merge_message handles empty stdout."""
    mock_run.return_value.returncode = 0
    mock_run.return_value.stdout = ""
    assert _merge_message() == ""


##############################################################################
# main() - detect increment classification
##############################################################################


def _run_main(
    capsys: pytest.CaptureFixture,
    version: str | None = "0.5.0",
    parent_ver: str | None = "0.4.0",
    merge_msg: str = "feat: add widget",
    github_event: str | None = None,
) -> None:
    """Run main() with mocked dependencies.

    Parameters
    ----------
    capsys : pytest.CaptureFixture
        pytest fixture for capturing stdout.
    version : str or None
        Current version from pyproject.toml.
    parent_ver : str or None
        Parent version from git.
    merge_msg : str
        Merge commit message.
    github_event : str or None
        GITHUB_EVENT_NAME env value (None = not set).
    """
    # Patch at the import site in detect_increment (direct imports)
    with (
        patch(
            "anvil.services.vault.detect_increment.read_version",
            return_value=version,
        ),
        patch(
            "anvil.services.vault.detect_increment.parent_version",
            return_value=parent_ver,
        ),
        patch(
            "anvil.services.vault.detect_increment.classify_increment",
            wraps=lambda msg: (
                "MAJOR" if "BREAKING" in msg.upper() else "MINOR"
                if msg.startswith("feat") else "PATCH"
                if msg.startswith("fix") else "NONE"
            ),
        ),
        patch(
            "anvil.services.vault.detect_increment._merge_message",
            return_value=merge_msg,
        ),
        patch.object(sys, "exit"),
    ):
        if github_event is not None:
            with patch.dict(os.environ, {"GITHUB_EVENT_NAME": github_event}):
                main()
        else:
            main()


def test_main_feat_minor(capsys: pytest.CaptureFixture) -> None:
    """A 'feat' merge message classifies as MINOR."""
    _run_main(capsys, merge_msg="feat: add widget", version="0.5.0", parent_ver="0.5.0")
    captured = capsys.readouterr()
    assert "increment=MINOR" in captured.out
    assert "version_changed=true" in captured.out


def test_main_fix_patch(capsys: pytest.CaptureFixture) -> None:
    """A 'fix' merge message classifies as PATCH."""
    _run_main(capsys, merge_msg="fix: resolve bug", version="0.5.0", parent_ver="0.5.0")
    captured = capsys.readouterr()
    assert "increment=PATCH" in captured.out
    assert "version_changed=true" in captured.out


def test_main_breaking_major(capsys: pytest.CaptureFixture) -> None:
    """A message containing BREAKING CHANGE classifies as MAJOR."""
    _run_main(
        capsys,
        merge_msg="feat: big change\n\nBREAKING CHANGE: api changed",
        version="0.5.0",
        parent_ver="0.5.0",
    )
    captured = capsys.readouterr()
    assert "increment=MAJOR" in captured.out
    assert "version_changed=true" in captured.out


def test_main_chore_none(capsys: pytest.CaptureFixture) -> None:
    """A chore merge message classifies as NONE."""
    _run_main(
        capsys,
        merge_msg="chore: update deps",
        version="0.5.0",
        parent_ver="0.5.0",
    )
    captured = capsys.readouterr()
    assert "increment=NONE" in captured.out
    assert "version_changed=false" in captured.out


def test_main_version_changed_skip(capsys: pytest.CaptureFixture) -> None:
    """When prev and current differ, increment=SKIP."""
    _run_main(capsys, version="0.6.0", parent_ver="0.5.0", merge_msg="feat: x")
    captured = capsys.readouterr()
    assert "increment=SKIP" in captured.out
    assert "version_changed=true" in captured.out


def test_main_workflow_dispatch_patch(capsys: pytest.CaptureFixture) -> None:
    """workflow_dispatch event forces PATCH increment."""
    _run_main(capsys, github_event="workflow_dispatch", merge_msg="")
    captured = capsys.readouterr()
    assert "increment=PATCH" in captured.out
    assert "version_changed=true" in captured.out


def test_main_no_parent_version(capsys: pytest.CaptureFixture) -> None:
    """When parent version is None, version_prev='none'."""
    _run_main(capsys, parent_ver=None, merge_msg="fix: init")
    captured = capsys.readouterr()
    assert "version_prev=none" in captured.out
    assert "increment=PATCH" in captured.out


def test_main_outputs_version(capsys: pytest.CaptureFixture) -> None:
    """version, version_current, version_prev are always printed."""
    _run_main(capsys, version="0.5.0", parent_ver="0.4.0")
    captured = capsys.readouterr()
    assert "version=0.5.0" in captured.out
    assert "version_current=0.5.0" in captured.out
    assert "version_prev=0.4.0" in captured.out


def test_main_unknown_version(capsys: pytest.CaptureFixture) -> None:
    """When read_version returns None, version prints as 'unknown'."""
    _run_main(capsys, version=None, parent_ver=None)
    captured = capsys.readouterr()
    assert "version=unknown" in captured.out
    assert "version_prev=none" in captured.out