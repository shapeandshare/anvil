#!/usr/bin/env python3
"""Guarded-imports checker — thin wrapper delegating to ``anvil-vault check-guarded-imports``.

Retained for backward compatibility. After the transition period, use
``anvil-vault check-guarded-imports`` directly.
"""

from __future__ import annotations

import subprocess
import sys


def main() -> None:
    """CLI entry point — delegate to ``anvil-vault check-guarded-imports``."""
    cmd = ["anvil-vault", "check-guarded-imports"]
    cmd.extend(sys.argv[1:])
    result = subprocess.run(cmd)
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()