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

import re
import subprocess
import sys

# Allowlist pattern for vault directory paths: only safe path characters.
_SAFE_PATH_RE = re.compile(r"^[\w./\\-]+$")


def main() -> None:
    """CLI entry point — delegate to ``anvil-vault audit``."""
    cmd = ["anvil-vault", "audit"]
    args = sys.argv[1:]
    # Legacy positional vault_dir arg -> --vault-dir
    if args and not args[0].startswith("-"):
        val = args.pop(0)
        if not _SAFE_PATH_RE.match(val):
            sys.exit(f"error: invalid vault directory: {val!r}")
        cmd.append("--vault-dir")
        cmd.append(val)
    cmd.extend(args)
    result = subprocess.run(cmd, check=False)
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
