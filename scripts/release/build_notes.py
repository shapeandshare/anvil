#!/usr/bin/env python3
"""Thin wrapper — delegates to ``anvil-vault build-notes``.

Retained for backward compatibility and local use. After the transition
period, use ``anvil-vault build-notes`` directly.
"""

from __future__ import annotations

import subprocess
import sys


def main() -> None:
    """CLI entry point — delegate to ``anvil-vault build-notes``."""
    cmd = ["anvil-vault", "build-notes"]
    cmd.extend(sys.argv[1:])
    result = subprocess.run(cmd)
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
