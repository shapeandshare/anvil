# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Detect whether the project version changed since the parent commit.

Used by the auto-bump workflow to decide whether to open a patch-bump PR.
"""

from __future__ import annotations

import sys

from .._shared.version_utils import parent_version, read_version


def main() -> None:
    """Print ``key=value`` lines to stdout for ``$GITHUB_OUTPUT``."""
    current = read_version() or "unknown"
    prev = parent_version() or "none"

    print(f"version_current={current}")
    print(f"version_prev={prev}")
    print(f"needs_bump={'true' if current == prev else 'false'}")
    sys.exit(0)


if __name__ == "__main__":
    main()