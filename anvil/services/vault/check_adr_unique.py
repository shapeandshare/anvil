# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""ADR uniqueness checker: detects duplicate ADR-0NN identifiers.

Enforces FR-011: every recorded architecture decision MUST have a unique
identifier; the system MUST detect and reject duplicate identifiers.

Scans ``docs/vault/Decisions/`` for ``ADR-0NN-*.md`` files, extracts the
``ADR-0NN`` identifier, and reports any duplicates or off-pattern files.
Exits 0 if no issues, 1 if duplicates or off-pattern files exist.
"""

from __future__ import annotations

import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path

# Match ADR-0NN-*.md files.
_ADR_PATTERN = re.compile(r"(.+\.md)$")


@dataclass
class ADRIssue:
    """A detected issue with an ADR file."""

    file: str
    message: str


def _extract_adr_numbers(
    files: set[Path],
) -> tuple[dict[str, list[Path]], list[ADRIssue]]:
    """Extract ADR identifiers from a set of file paths.

    Parameters
    ----------
    files : set of Path
        Files in the Decisions directory.

    Returns
    -------
    tuple[dict[str, list[Path]], list[ADRIssue]]
        A mapping of ADR identifier → file paths, and a list of issues
        for non-conforming files.
    """
    numbers: dict[str, list[Path]] = {}
    issues: list[ADRIssue] = []
    adr_count = 0

    for f in sorted(files):
        # Skip non-ADR files (README, template, etc.)
        name = f.name

        # Skip the template and README
        if name in ("ADR-template.md", "README.md"):
            continue

        # Match standard ADR-0NN-*.md pattern
        m = re.match(r"^(ADR-\d{3})-.+\.md$", name)
        if m:
            adr_id = m.group(1)
            adr_count += 1
            if adr_id not in numbers:
                numbers[adr_id] = []
            numbers[adr_id].append(f)
            continue

        # Match off-pattern files that contain ADR-like numbers
        m2 = re.match(r"^(\d{3})-.+\.md$", name)
        if m2:
            issues.append(
                ADRIssue(
                    str(f),
                    f"File '{name}' uses a numeric prefix ({m2.group(1)}) but "
                    f"does not follow 'ADR-0NN-*' naming convention. "
                    f"Rename to 'ADR-{m2.group(1)}-*'.",
                )
            )
            continue

        # File doesn't match any ADR pattern — skip silently
        # (it's non-ADR content like a template)

    return numbers, issues


def _find_duplicates(numbers: dict[str, list[Path]]) -> list[ADRIssue]:
    """Find duplicate ADR identifiers.

    Parameters
    ----------
    numbers : dict[str, list[Path]]
        ADR identifier → list of file paths.

    Returns
    -------
    list of ADRIssue
    """
    issues: list[ADRIssue] = []
    for adr_id, files in numbers.items():
        if len(files) > 1:
            files_str = ", ".join(str(f.relative_to(f.parents[2])) for f in files)
            issues.append(
                ADRIssue(
                    str(files[0]),
                    f"Duplicate ADR identifier: {adr_id} appears in "
                    f"{len(files)} files: {files_str}. "
                    f"Each ADR must have a unique number.",
                )
            )
    return issues


def _validate_adrs(decisions_dir: Path) -> list[ADRIssue]:
    """Validate all ADR files in a decisions directory.

    Parameters
    ----------
    decisions_dir : pathlib.Path
        Path to the Decisions directory.

    Returns
    -------
    list of ADRIssue
    """
    if not decisions_dir.exists():
        return [ADRIssue(str(decisions_dir), "Decisions directory not found.")]

    files = set(decisions_dir.iterdir())
    numbers, extract_issues = _extract_adr_numbers(files)
    duplicate_issues = _find_duplicates(numbers)

    return extract_issues + duplicate_issues


def main() -> None:
    """CLI entry point."""
    decisions_dir = Path(os.environ.get("ANVIL_DECISIONS_DIR", "docs/vault/Decisions"))

    issues = _validate_adrs(decisions_dir)

    if issues:
        for issue in issues:
            print(f"ISSUE: {issue.message}")
        print(f"\n{len(issues)} issue(s) found.")
        sys.exit(1)
    else:
        print(f"OK: All ADRs in {decisions_dir} valid and unique.")
        sys.exit(0)


if __name__ == "__main__":
    main()
