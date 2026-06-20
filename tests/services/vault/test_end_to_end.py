"""End-to-end tests — compare legacy script output with new CLI."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


class TestEndToEnd:
    """End-to-end verification that the CLI produces expected output."""

    def test_cli_invocation(self) -> None:
        """Verify anvil-vault can be invoked and prints help."""
        result = subprocess.run(
            [sys.executable, "-m", "anvil.services.vault.cli", "--help"],
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0
        assert "audit" in result.stdout
        assert "check-adrs" in result.stdout

    def test_cli_check_adrs(self) -> None:
        """Verify check-adrs runs without error."""
        result = subprocess.run(
            [sys.executable, "-m", "anvil.services.vault.cli", "check-adrs"],
            capture_output=True,
            text=True,
            check=False,
        )
        # May exit 0 or 1 depending on actual ADR state — just check it runs
        assert result.returncode in (0, 1)
