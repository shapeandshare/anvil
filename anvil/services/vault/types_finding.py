# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Finding model — a single issue detected during vault auditing."""

from __future__ import annotations

from pydantic import BaseModel


class Finding(BaseModel):
    """A single issue detected during vault auditing.

    Attributes
    ----------
    note_path : str
        File path relative to vault root.
    line : int
        Line number (0 if file-level).
    rule : str
        Rule identifier (e.g. ``FM-001``, ``WL-003``).
    message : str
        Human-readable description.
    severity : str
        ``ERROR``, ``WARN``, or ``SKIPPED``.
    fixable : bool
        Whether auto-fix is available via ``--apply``.
    """

    note_path: str
    line: int = 0
    rule: str = ""
    message: str = ""
    severity: str = ""
    fixable: bool = False