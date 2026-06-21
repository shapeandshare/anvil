# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Build GitHub release notes from CHANGELOG.md and optional PR body.

Reads the current version from ``pyproject.toml``, extracts the corresponding
entry from ``CHANGELOG.md``, and appends the ``PR_BODY`` environment variable
if set. Writes ``release-notes.md`` in the current directory.
"""

from __future__ import annotations

import os
import re
import sys

from .._shared.version_utils import read_version


def _extract_changelog_entry(version: str) -> str | None:
    """Return the CHANGELOG.md section for *version*, or ``None``."""
    try:
        with open("CHANGELOG.md") as f:
            content = f.read()
    except FileNotFoundError:
        return None

    pattern = rf"^## v{re.escape(version)}\s*$(.*?)(?=^## v|\Z)"
    m = re.search(pattern, content, re.MULTILINE | re.DOTALL)
    if not m:
        return None

    entry = m.group(1).strip()
    entry = re.sub(r"^---+$", "", entry, flags=re.MULTILINE)
    entry = entry.strip()
    return entry or None


def main() -> None:
    """Build ``release-notes.md`` in the current directory."""
    version = read_version()
    if version is None:
        print("error: version not found in pyproject.toml", file=sys.stderr)
        sys.exit(1)

    notes_file = "release-notes.md"
    lines = [f"## anvil v{version}", ""]

    entry = _extract_changelog_entry(version)
    if entry:
        lines.append("### Changelog")
        lines.append("")
        lines.append(entry)
        lines.append("")

    pr_body = os.environ.get("PR_BODY", "")
    if pr_body:
        lines.append("### Release Notes")
        lines.append("")
        lines.append(pr_body)
        lines.append("")

    with open(notes_file, "w") as f:
        f.write("\n".join(lines) + "\n")

    print(f"release-notes.md written (v{version})")
    sys.exit(0)


if __name__ == "__main__":
    main()
