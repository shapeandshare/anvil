# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Detect version increment from merge commit message.

Classifies a merge commit by conventional commit type
(``feat`` → MINOR, ``fix`` → PATCH, ``BREAKING CHANGE`` → MAJOR).
Used by the release workflow to determine the version bump.
"""

from __future__ import annotations

import os
import subprocess
import sys

from .._shared.version_utils import classify_increment, parent_version, read_version


def _merge_message() -> str:
    """Return the most recent commit's full message."""
    result = subprocess.run(
        ["git", "log", "-1", "--format=%B"],
        capture_output=True,
        text=True,
    )
    return result.stdout.strip() if result.returncode == 0 else ""


def main() -> None:
    """Print ``key=value`` lines to stdout for ``$GITHUB_OUTPUT``."""
    current = read_version() or "unknown"
    prev = parent_version()

    print(f"version={current}")
    print(f"version_current={current}")
    print(f"version_prev={prev or 'none'}")

    if os.environ.get("GITHUB_EVENT_NAME") == "workflow_dispatch":
        print("increment=PATCH")
        print("version_changed=true")
        return

    if prev is not None and current != prev:
        print("increment=SKIP")
        print("version_changed=true")
        return

    increment = classify_increment(_merge_message())
    print(f"increment={increment}")
    print(f"version_changed={'true' if increment != 'NONE' else 'false'}")
    sys.exit(0)


if __name__ == "__main__":
    main()
