"""Tests for anvil-backup CLI argument parser and exit codes."""

from anvil.services.backup.cli import build_parser, main


class TestCLIParser:
    """Parser structure and argument validation."""

    def test_parser_accepts_create(self):
        parser = build_parser()
        args = parser.parse_args(["create"])
        assert args.command == "create"

    def test_parser_accepts_list(self):
        parser = build_parser()
        args = parser.parse_args(["list"])
        assert args.command == "list"

    def test_parser_accepts_list_with_flags(self):
        parser = build_parser()
        args = parser.parse_args(["list", "--include-safety", "--json"])
        assert args.command == "list"
        assert args.include_safety is True
        assert args.json is True

    def test_parser_accepts_show(self):
        parser = build_parser()
        args = parser.parse_args(["show", "some-backup-id"])
        assert args.command == "show"
        assert args.backup_id == "some-backup-id"

    def test_parser_accepts_restore(self):
        parser = build_parser()
        args = parser.parse_args(["restore", "backup-123"])
        assert args.command == "restore"
        assert args.backup_id == "backup-123"

    def test_parser_accepts_delete(self):
        parser = build_parser()
        args = parser.parse_args(["delete", "backup-123"])
        assert args.command == "delete"
        assert args.backup_id == "backup-123"

    def test_parser_accepts_verify(self):
        parser = build_parser()
        args = parser.parse_args(["verify", "backup-123"])
        assert args.command == "verify"
        assert args.backup_id == "backup-123"

    def test_parser_no_args_exits(self):
        """Running the CLI with no args should call sys.exit(1)."""
        import sys
        try:
            main([])
        except SystemExit as e:
            assert e.code == 1

    def test_parser_accepts_status(self):
        parser = build_parser()
        args = parser.parse_args(["status"])
        assert args.command == "status"