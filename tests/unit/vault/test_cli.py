# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Unit tests for CLI entry points — anvil-vault subcommands.

Tests argument parsing, dispatch, and the ``_cmd_audit`` handler
(which exercises the ``VaultHealthService`` orchestrator).  All
service-layer calls are mocked to keep tests fast and isolated.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from anvil.services.vault.cli import build_parser, main
from anvil.services.vault.types_finding import Finding
from anvil.services.vault.types_graph_health_report import GraphHealthReport
from anvil.services.vault.types_health_score import HealthScore
from anvil.services.vault.types_mechanical_report import MechanicalReport


######################################################################
# Helpers
######################################################################


def _make_mech_report(
    errors: list[Finding] | None = None,
    warnings: list[Finding] | None = None,
) -> MechanicalReport:
    """Build a ``MechanicalReport`` with the given findings."""
    report = MechanicalReport()
    for f in errors or []:
        report.add(f)
    for f in warnings or []:
        report.add(f)
    return report


def _make_gh_report(score: float = 100.0) -> GraphHealthReport:
    """Build a ``GraphHealthReport`` with the given health score."""
    return GraphHealthReport(
        notes_scanned=10,
        health_score=HealthScore(overall=score),
    )


def _finding(
    note_path: str = "test.md",
    severity: str = "ERROR",
    message: str = "test finding",
    fixable: bool = False,
) -> Finding:
    return Finding(
        note_path=note_path,
        line=1,
        rule="TEST",
        message=message,
        severity=severity,
        fixable=fixable,
    )


######################################################################
# Parser tests
######################################################################


class TestBuildParser:
    """Tests for ``build_parser`` — all subcommands parse correctly."""

    def test_audit_subcommand(self) -> None:
        """Verify ``audit`` subcommand parses all flags."""
        parser = build_parser()
        args = parser.parse_args(
            ["audit", "--vault-dir", "custom/vault", "--apply", "--skip-graph-health"]
        )
        assert args.command == "audit"
        assert args.vault_dir == "custom/vault"
        assert args.apply is True
        assert args.diff is False
        assert args.skip_graph_health is True

    def test_audit_defaults(self) -> None:
        """Verify ``audit`` defaults are correct."""
        parser = build_parser()
        args = parser.parse_args(["audit"])
        assert args.command == "audit"
        assert args.vault_dir == "docs/vault"
        assert args.apply is False
        assert args.diff is False
        assert args.skip_graph_health is False

    def test_audit_diff_flag(self) -> None:
        """Verify ``--diff`` flag parses."""
        parser = build_parser()
        args = parser.parse_args(["audit", "--diff"])
        assert args.diff is True

    def test_check_adrs_subcommand(self) -> None:
        """Verify ``check-adrs`` subcommand."""
        parser = build_parser()
        args = parser.parse_args(["check-adrs", "--decisions-dir", "decisions"])
        assert args.command == "check-adrs"
        assert args.decisions_dir == "decisions"

    def test_check_adrs_default(self) -> None:
        """Verify ``check-adrs`` default decisions-dir."""
        parser = build_parser()
        args = parser.parse_args(["check-adrs"])
        assert args.decisions_dir == "docs/vault/Decisions"

    def test_check_guarded_imports(self) -> None:
        """Verify ``check-guarded-imports`` subcommand."""
        parser = build_parser()
        args = parser.parse_args(["check-guarded-imports"])
        assert args.command == "check-guarded-imports"
        assert args.source_dir == "anvil"

    def test_check_guarded_imports_custom_source(self) -> None:
        """Verify custom ``--source-dir``."""
        parser = build_parser()
        args = parser.parse_args(["check-guarded-imports", "--source-dir", "src"])
        assert args.source_dir == "src"

    def test_check_bump_scope(self) -> None:
        """Verify ``check-bump-scope`` subcommand."""
        parser = build_parser()
        args = parser.parse_args(["check-bump-scope"])
        assert args.command == "check-bump-scope"

    def test_bump_subcommand(self) -> None:
        """Verify ``bump`` subcommand with increment."""
        parser = build_parser()
        args = parser.parse_args(["bump", "--increment", "MAJOR"])
        assert args.command == "bump"
        assert args.increment == "MAJOR"

    def test_bump_invalid_increment(self) -> None:
        """Verify invalid increment raises error."""
        parser = build_parser()
        with pytest.raises(SystemExit):
            parser.parse_args(["bump", "--increment", "INVALID"])

    def test_bump_patch(self) -> None:
        """Verify ``bump-patch`` subcommand."""
        parser = build_parser()
        args = parser.parse_args(["bump-patch"])
        assert args.command == "bump-patch"

    def test_detect_increment(self) -> None:
        """Verify ``detect-increment`` subcommand."""
        parser = build_parser()
        args = parser.parse_args(["detect-increment"])
        assert args.command == "detect-increment"

    def test_check_version(self) -> None:
        """Verify ``check-version`` subcommand."""
        parser = build_parser()
        args = parser.parse_args(["check-version"])
        assert args.command == "check-version"

    def test_build_notes(self) -> None:
        """Verify ``build-notes`` subcommand."""
        parser = build_parser()
        args = parser.parse_args(["build-notes"])
        assert args.command == "build-notes"

    def test_migrate_specs_dry_run(self) -> None:
        """Verify ``migrate-specs --dry-run``."""
        parser = build_parser()
        args = parser.parse_args(
            ["migrate-specs", "--dry-run", "--vault-dir", "vault", "--specs-dir", "sp"]
        )
        assert args.command == "migrate-specs"
        assert args.dry_run is True
        assert args.verify_only is False
        assert args.apply is False
        assert args.vault_dir == "vault"
        assert args.specs_dir == "sp"

    def test_migrate_specs_verify_only(self) -> None:
        """Verify ``migrate-specs --verify-only``."""
        parser = build_parser()
        args = parser.parse_args(["migrate-specs", "--verify-only"])
        assert args.verify_only is True

    def test_migrate_specs_apply(self) -> None:
        """Verify ``migrate-specs --apply``."""
        parser = build_parser()
        args = parser.parse_args(["migrate-specs", "--apply"])
        assert args.apply is True

    def test_migrate_specs_requires_flag(self) -> None:
        """Verify ``migrate-specs`` fails without a required flag."""
        parser = build_parser()
        with pytest.raises(SystemExit):
            parser.parse_args(["migrate-specs"])

    def test_check_init_py(self) -> None:
        """Verify ``check-init-py`` subcommand."""
        parser = build_parser()
        args = parser.parse_args(["check-init-py"])
        assert args.command == "check-init-py"

    def test_check_relative_imports(self) -> None:
        """Verify ``check-relative-imports`` subcommand."""
        parser = build_parser()
        args = parser.parse_args(["check-relative-imports"])
        assert args.command == "check-relative-imports"

    def test_check_one_class(self) -> None:
        """Verify ``check-one-class`` subcommand."""
        parser = build_parser()
        args = parser.parse_args(["check-one-class"])
        assert args.command == "check-one-class"

    def test_check_import_placement(self) -> None:
        """Verify ``check-import-placement`` subcommand."""
        parser = build_parser()
        args = parser.parse_args(["check-import-placement"])
        assert args.command == "check-import-placement"

    def test_check_nesting(self) -> None:
        """Verify ``check-nesting`` subcommand."""
        parser = build_parser()
        args = parser.parse_args(["check-nesting"])
        assert args.command == "check-nesting"

    def test_check_py_typed(self) -> None:
        """Verify ``check-py-typed`` subcommand."""
        parser = build_parser()
        args = parser.parse_args(["check-py-typed"])
        assert args.command == "check-py-typed"

    def test_check_core_deps(self) -> None:
        """Verify ``check-core-deps`` subcommand."""
        parser = build_parser()
        args = parser.parse_args(["check-core-deps"])
        assert args.command == "check-core-deps"

    def test_check_core_deps_custom_source(self) -> None:
        """Verify ``check-core-deps`` with custom source."""
        parser = build_parser()
        args = parser.parse_args(["check-core-deps", "--source-dir", "anvil/core"])
        assert args.source_dir == "anvil/core"

    def test_check_layers(self) -> None:
        """Verify ``check-layers`` subcommand."""
        parser = build_parser()
        args = parser.parse_args(["check-layers"])
        assert args.command == "check-layers"

    def test_help_output_lists_all_subcommands(self) -> None:
        """Verify ``--help`` lists all expected subcommands."""
        parser = build_parser()
        help_text = parser.format_help()
        expected = [
            "audit",
            "check-adrs",
            "check-guarded-imports",
            "check-bump-scope",
            "bump",
            "bump-patch",
            "detect-increment",
            "check-version",
            "build-notes",
            "migrate-specs",
            "check-init-py",
            "check-relative-imports",
            "check-one-class",
            "check-import-placement",
            "check-nesting",
            "check-py-typed",
            "check-core-deps",
            "check-layers",
        ]
        for cmd in expected:
            assert cmd in help_text, f"Missing subcommand: {cmd}"

    def test_no_args_prints_help(self) -> None:
        """Verify no args prints help and exits 1."""
        parser = build_parser()
        args = parser.parse_args([])
        assert args.command is None


######################################################################
# Dispatch tests
######################################################################


class TestMainDispatch:
    """Tests for ``main()`` dispatch to the correct handler."""

    @patch("anvil.services.vault.cli.check_adr_unique_main")
    def test_dispatch_check_adrs(
        self, mock_check: MagicMock
    ) -> None:
        """Verify ``check-adrs`` dispatches correctly."""
        with patch.dict("os.environ", clear=True):
            main(["check-adrs"])
        mock_check.assert_called_once()

    @patch("anvil.services.vault.cli.check_guarded_imports_main")
    def test_dispatch_check_guarded_imports(
        self, mock_check: MagicMock
    ) -> None:
        """Verify ``check-guarded-imports`` dispatches correctly."""
        with patch.dict("os.environ", clear=True):
            main(["check-guarded-imports"])
        mock_check.assert_called_once()

    @patch("anvil.services.vault.cli.check_bump_scope_main")
    def test_dispatch_check_bump_scope(
        self, mock_check: MagicMock
    ) -> None:
        """Verify ``check-bump-scope`` dispatches correctly."""
        with patch.dict("os.environ", clear=True):
            main(["check-bump-scope"])
        mock_check.assert_called_once()

    @patch("anvil.services.vault.cli.bump_version_main")
    def test_dispatch_bump_patch(
        self, mock_check: MagicMock
    ) -> None:
        """Verify ``bump-patch`` dispatches correctly."""
        main(["bump-patch"])
        mock_check.assert_called_once()

    @patch("anvil.services.vault.cli.bump_main")
    def test_dispatch_bump(self, mock_check: MagicMock) -> None:
        """Verify ``bump`` dispatches correctly."""
        main(["bump", "--increment", "PATCH"])
        mock_check.assert_called_once_with(increment="PATCH")

    @patch("anvil.services.vault.cli.bump_main")
    def test_dispatch_bump_minor(self, mock_check: MagicMock) -> None:
        """Verify ``bump --increment MINOR`` dispatches."""
        main(["bump", "--increment", "MINOR"])
        mock_check.assert_called_once_with(increment="MINOR")

    @patch("anvil.services.vault.cli.detect_increment_main")
    def test_dispatch_detect_increment(
        self, mock_check: MagicMock
    ) -> None:
        """Verify ``detect-increment`` dispatches correctly."""
        main(["detect-increment"])
        mock_check.assert_called_once()

    @patch("anvil.services.vault.cli.check_version_main")
    def test_dispatch_check_version(
        self, mock_check: MagicMock
    ) -> None:
        """Verify ``check-version`` dispatches correctly."""
        main(["check-version"])
        mock_check.assert_called_once()

    @patch("anvil.services.vault.cli.build_notes_main")
    def test_dispatch_build_notes(
        self, mock_check: MagicMock
    ) -> None:
        """Verify ``build-notes`` dispatches correctly."""
        main(["build-notes"])
        mock_check.assert_called_once()

    @patch("anvil.services.vault.cli.migrate_specs_run")
    def test_dispatch_migrate_specs_dry_run(
        self, mock_check: MagicMock
    ) -> None:
        """Verify ``migrate-specs --dry-run`` dispatches."""
        mock_check.return_value = 0
        with pytest.raises(SystemExit):
            main(["migrate-specs", "--dry-run"])
        mock_check.assert_called_once_with(
            vault_dir="docs/vault",
            specs_dir="specs",
            dry_run=True,
            verify_only=False,
            apply=False,
        )

    @patch("anvil.services.vault.cli.migrate_specs_run")
    def test_dispatch_migrate_specs_apply(
        self, mock_check: MagicMock
    ) -> None:
        """Verify ``migrate-specs --apply`` dispatches."""
        mock_check.return_value = 0
        with pytest.raises(SystemExit):
            main(["migrate-specs", "--apply", "--vault-dir", "my-vault"])
        mock_check.assert_called_once_with(
            vault_dir="my-vault",
            specs_dir="specs",
            dry_run=False,
            verify_only=False,
            apply=True,
        )

    @patch("anvil.services.vault.cli.check_init_py_ownership_main")
    def test_dispatch_check_init_py(
        self, mock_check: MagicMock
    ) -> None:
        """Verify ``check-init-py`` dispatches."""
        main(["check-init-py"])
        mock_check.assert_called_once()

    @patch("anvil.services.vault.cli.check_relative_imports_main")
    def test_dispatch_check_relative_imports(
        self, mock_check: MagicMock
    ) -> None:
        """Verify ``check-relative-imports`` dispatches."""
        main(["check-relative-imports"])
        mock_check.assert_called_once()

    @patch("anvil.services.vault.cli.check_one_class_main")
    def test_dispatch_check_one_class(
        self, mock_check: MagicMock
    ) -> None:
        """Verify ``check-one-class`` dispatches."""
        with patch.dict("os.environ", clear=True):
            main(["check-one-class"])
        mock_check.assert_called_once()

    @patch("anvil.services.vault.cli.check_import_placement_main")
    def test_dispatch_check_import_placement(
        self, mock_check: MagicMock
    ) -> None:
        """Verify ``check-import-placement`` dispatches."""
        main(["check-import-placement"])
        mock_check.assert_called_once()

    @patch("anvil.services.vault.cli.check_nesting_depth_main")
    def test_dispatch_check_nesting(
        self, mock_check: MagicMock
    ) -> None:
        """Verify ``check-nesting`` dispatches."""
        main(["check-nesting"])
        mock_check.assert_called_once()

    @patch("anvil.services.vault.cli.check_py_typed_main")
    def test_dispatch_check_py_typed(
        self, mock_check: MagicMock
    ) -> None:
        """Verify ``check-py-typed`` dispatches."""
        main(["check-py-typed"])
        mock_check.assert_called_once()

    @patch("anvil.services.vault.cli.check_core_deps_main")
    def test_dispatch_check_core_deps(
        self, mock_check: MagicMock
    ) -> None:
        """Verify ``check-core-deps`` dispatches."""
        with patch.dict("os.environ", clear=True):
            main(["check-core-deps"])
        mock_check.assert_called_once()

    @patch("anvil.services.vault.cli.check_layer_boundaries_main")
    def test_dispatch_check_layers(
        self, mock_check: MagicMock
    ) -> None:
        """Verify ``check-layers`` dispatches."""
        main(["check-layers"])
        mock_check.assert_called_once()

    def test_unknown_command_exits(self) -> None:
        """Verify unknown command exits with code 2 (argparse error)."""
        with pytest.raises(SystemExit) as exc:
            main(["nonexistent"])
        assert exc.value.code == 2


######################################################################
# Audit command tests
######################################################################


class TestCmdAudit:
    """Tests for the ``audit`` subcommand handler (``_cmd_audit``)."""

    def test_audit_no_issues(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Verify audit with no issues prints success and exits 0."""
        mock_svc = MagicMock()
        mock_svc.run_full_audit = AsyncMock(
            return_value=(
                _make_mech_report(),
                _make_gh_report(score=95.0),
            )
        )

        with patch(
            "anvil.services.vault.cli.VaultHealthService",
            return_value=mock_svc,
        ):
            main(["audit"])

        captured = capsys.readouterr()
        assert "0 errors" in captured.out
        assert "95.0" in captured.out

    def test_audit_with_errors_exits_1(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Verify audit with errors exits 1."""
        mock_svc = MagicMock()
        mock_svc.run_full_audit = AsyncMock(
            return_value=(
                _make_mech_report(
                    errors=[
                        _finding(note_path="bad.md", message="missing field"),
                    ]
                ),
                _make_gh_report(),
            )
        )

        with patch(
            "anvil.services.vault.cli.VaultHealthService",
            return_value=mock_svc,
        ):
            with pytest.raises(SystemExit) as exc:
                main(["audit"])
        assert exc.value.code == 1
        captured = capsys.readouterr()
        assert "1 errors" in captured.out
        assert "bad.md" in captured.out
        assert "missing field" in captured.out

    def test_audit_with_warnings(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Verify warnings are printed but don't cause exit."""
        mock_svc = MagicMock()
        mock_svc.run_full_audit = AsyncMock(
            return_value=(
                _make_mech_report(
                    warnings=[
                        _finding(
                            note_path="warn.md",
                            severity="WARN",
                            message="minor issue",
                        ),
                    ]
                ),
                _make_gh_report(),
            )
        )

        with patch(
            "anvil.services.vault.cli.VaultHealthService",
            return_value=mock_svc,
        ):
            main(["audit"])

        captured = capsys.readouterr()
        assert "0 errors" in captured.out
        assert "1 warnings" in captured.out
        assert "warn.md" in captured.out
        assert "minor issue" in captured.out

    def test_audit_no_graph_health(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Verify ``--skip-graph-health`` skips graph health."""
        mock_svc = MagicMock()
        mock_svc.run_full_audit = AsyncMock(
            return_value=(
                _make_mech_report(),
                None,
            )
        )

        with patch(
            "anvil.services.vault.cli.VaultHealthService",
            return_value=mock_svc,
        ):
            main(["audit", "--skip-graph-health"])

        captured = capsys.readouterr()
        assert "0 errors" in captured.out
        assert "Graph health" not in captured.out

    def test_audit_diff_mode(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Verify ``--diff`` mode prints proposed fixes (still exits 1)."""
        fixable_error = _finding(
            note_path="fixable.md", message="can be fixed", fixable=True
        )
        unfixable_error = _finding(
            note_path="broken.md", message="cannot be fixed", fixable=False
        )

        mock_svc = MagicMock()
        mock_svc.run_full_audit = AsyncMock(
            return_value=(
                _make_mech_report(errors=[fixable_error, unfixable_error]),
                None,
            )
        )

        with patch(
            "anvil.services.vault.cli.VaultHealthService",
            return_value=mock_svc,
        ):
            with pytest.raises(SystemExit) as exc:
                main(["audit", "--diff", "--skip-graph-health"])
        assert exc.value.code == 1
        captured = capsys.readouterr()
        assert "Diff mode" in captured.out
        assert "fixable.md" in captured.out
        assert "broken.md" not in captured.out  # unfixable not shown

    def test_audit_diff_mode_no_fixable(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Verify ``--diff`` with no fixable issues prints message."""
        unfixable = _finding(
            note_path="broken.md", message="cannot be fixed", fixable=False
        )

        mock_svc = MagicMock()
        mock_svc.run_full_audit = AsyncMock(
            return_value=(
                _make_mech_report(errors=[unfixable]),
                None,
            )
        )

        with patch(
            "anvil.services.vault.cli.VaultHealthService",
            return_value=mock_svc,
        ):
            with pytest.raises(SystemExit) as exc:
                main(["audit", "--diff", "--skip-graph-health"])
        assert exc.value.code == 1
        captured = capsys.readouterr()
        assert "No fixable issues found." in captured.out

    def test_audit_apply_mode(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Verify ``--apply`` mode prints fixed items (still exits 1)."""
        fixable = _finding(
            note_path="fixed.md", message="applied fix", fixable=True
        )

        mock_svc = MagicMock()
        mock_svc.run_full_audit = AsyncMock(
            return_value=(
                _make_mech_report(errors=[fixable]),
                None,
            )
        )

        with patch(
            "anvil.services.vault.cli.VaultHealthService",
            return_value=mock_svc,
        ):
            with pytest.raises(SystemExit) as exc:
                main(["audit", "--apply", "--skip-graph-health"])
        assert exc.value.code == 1
        captured = capsys.readouterr()
        assert "Apply mode" in captured.out
        assert "Fixed:" in captured.out
        assert "fixed.md" in captured.out

    def test_audit_apply_mode_no_fixable(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Verify ``--apply`` with no fixable issues prints message."""
        unfixable = _finding(
            note_path="broken.md", message="cannot be fixed", fixable=False
        )

        mock_svc = MagicMock()
        mock_svc.run_full_audit = AsyncMock(
            return_value=(
                _make_mech_report(errors=[unfixable]),
                None,
            )
        )

        with patch(
            "anvil.services.vault.cli.VaultHealthService",
            return_value=mock_svc,
        ):
            with pytest.raises(SystemExit) as exc:
                main(["audit", "--apply", "--skip-graph-health"])
        assert exc.value.code == 1
        captured = capsys.readouterr()
        assert "No fixable issues found." in captured.out

    def test_audit_with_errors_and_warnings(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Verify audit shows both errors and warnings."""
        mock_svc = MagicMock()
        mock_svc.run_full_audit = AsyncMock(
            return_value=(
                _make_mech_report(
                    errors=[
                        _finding(note_path="err.md", message="error thing"),
                    ],
                    warnings=[
                        _finding(
                            note_path="warn.md",
                            severity="WARN",
                            message="warn thing",
                        ),
                    ],
                ),
                _make_gh_report(),
            )
        )

        with patch(
            "anvil.services.vault.cli.VaultHealthService",
            return_value=mock_svc,
        ):
            with pytest.raises(SystemExit) as exc:
                main(["audit"])
        assert exc.value.code == 1

        captured = capsys.readouterr()
        assert "1 errors" in captured.out
        assert "1 warnings" in captured.out
        assert "[ERROR]" in captured.out
        assert "[WARN]" in captured.out


######################################################################
# CLI error handling
######################################################################


class TestMainErrorHandling:
    """Tests for error handling in ``main()``."""

    def test_no_command_prints_help_and_exits(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Verify no command prints help and exits 1."""
        with pytest.raises(SystemExit) as exc:
            main([])
        assert exc.value.code == 1
        captured = capsys.readouterr()
        assert "usage:" in captured.out

    def test_main_with_none_argv(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Verify ``main()`` with ``None`` argv (defaults to empty list)."""
        with patch.object(sys, "argv", ["anvil-vault"]):
            with pytest.raises(SystemExit) as exc:
                main()
        assert exc.value.code == 1
        captured = capsys.readouterr()
        assert "usage:" in captured.out