#!/usr/bin/env python3
"""Thin wrapper — delegates to ``anvil-vault check-version``.

Retained for backward compatibility and local use. After the transition
period, use ``anvil-vault check-version`` directly.
"""

from __future__ import annotations

import subprocess
import sys


def main() -> None:
    """CLI entry point — delegate to ``anvil-vault check-version``."""
    cmd = ["anvil-vault", "check-version"]
    cmd.extend(sys.argv[1:])
    result = subprocess.run(cmd)
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
