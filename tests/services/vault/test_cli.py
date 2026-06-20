"""Tests for CLI — anvil-vault subcommands."""

from __future__ import annotations

from pathlib import Path

from anvil.services.vault.cli import build_parser


class TestCLIParser:
    """Tests for the CLI argument parser."""

    def test_audit_subcommand(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["audit", "--vault-dir", "docs/vault"])
        assert args.command == "audit"
        assert args.vault_dir == "docs/vault"

    def test_audit_defaults(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["audit"])
        assert args.command == "audit"
        assert args.vault_dir == "docs/vault"
        assert args.apply is False
        assert args.diff is False
        assert args.skip_graph_health is False

    def test_audit_flags(self) -> None:
        parser = build_parser()
        args = parser.parse_args(
            ["audit", "--apply", "--skip-graph-health"]
        )
        assert args.apply is True
        assert args.skip_graph_health is True

    def test_check_adrs_subcommand(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["check-adrs"])
        assert args.command == "check-adrs"

    def test_check_guarded_imports(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["check-guarded-imports"])
        assert args.command == "check-guarded-imports"

    def test_check_bump_scope(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["check-bump-scope"])
        assert args.command == "check-bump-scope"

    def test_help_output(self) -> None:
        """Verify --help lists all 4 subcommands."""
        parser = build_parser()
        help_text = parser.format_help()
        assert "audit" in help_text
        assert "check-adrs" in help_text
        assert "check-guarded-imports" in help_text
        assert "check-bump-scope" in help_text
