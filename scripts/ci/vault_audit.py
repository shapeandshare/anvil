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

import sys


def main() -> None:
    """CLI entry point — delegate to ``anvil-vault audit``."""
    from anvil.services.vault.cli import main as audit_main

    args = ["audit"] + sys.argv[1:]
    # Translate legacy positional vault_dir arg to --vault-dir
    if len(args) > 1 and not args[1].startswith("-"):
        a = args[1]
        args = ["audit", "--vault-dir", a] + args[2:]
    audit_main(args)


if __name__ == "__main__":
    main()
