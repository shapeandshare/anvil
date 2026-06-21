# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

#!/usr/bin/env python3
"""Bump-scope guard — thin wrapper delegating to ``anvil-vault check-bump-scope``.

Retained for backward compatibility. After the transition period, use
``anvil-vault check-bump-scope`` directly.
"""

from __future__ import annotations

import subprocess
import sys


def main() -> None:
    """CLI entry point — delegate to ``anvil-vault check-bump-scope``."""
    cmd = ["anvil-vault", "check-bump-scope"]
    cmd.extend(sys.argv[1:])
    result = subprocess.run(cmd)
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
