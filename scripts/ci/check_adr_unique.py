#!/usr/bin/env python3
"""ADR uniqueness checker — thin wrapper delegating to ``anvil-vault check-adrs``.

Retained for backward compatibility. After the transition period, use
``anvil-vault check-adrs`` directly.
"""

from __future__ import annotations

import subprocess
import sys


def main() -> None:
    """CLI entry point — delegate to ``anvil-vault check-adrs``."""
    cmd = ["anvil-vault", "check-adrs"]
    cmd.extend(sys.argv[1:])
    result = subprocess.run(cmd)
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()