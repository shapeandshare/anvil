#!/usr/bin/env python3
"""Vault Audit — thin wrapper delegating to ``anvil-vault audit``.

This script is retained for backward compatibility during the transition
period. It delegates to the ``anvil-vault audit`` CLI command.

Direct use:
    python scripts/ci/vault_audit.py docs/vault
    python scripts/ci/vault_audit.py docs/vault --apply

After the transition period, remove this file and use ``anvil-vault audit``
directly (or via ``make vault-audit``).
"""

from __future__ import annotations

import subprocess
import sys


def main() -> None:
    """CLI entry point — delegate to ``anvil-vault audit``."""
    cmd = ["anvil-vault", "audit"]
    args = sys.argv[1:]
    # Legacy positional vault_dir arg -> --vault-dir
    if args and not args[0].startswith("-"):
        cmd.append("--vault-dir")
        cmd.append(args.pop(0))
    cmd.extend(args)
    result = subprocess.run(cmd)
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
