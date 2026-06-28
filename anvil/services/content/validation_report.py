# one-class:allow — ValidationProblem is a sub-type of ValidationReport
# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Validation result types for content ingestion gates.

``ValidationReport`` and ``ValidationProblem`` model the outcome of
running validation checks over a staged ingestion batch. Each problem
identifies the gate that failed and the entry (if any) responsible.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class ValidationProblem(BaseModel):
    """A single validation failure or warning from a gate.

    Parameters
    ----------
    gate_name : str
        Name of the validation gate that produced this problem
        (e.g. ``"size_limit"``, ``"content_type"``).
    entry_path : str | None
        Path of the entry that triggered the problem, or ``None``
        when the problem is batch-level.
    reason : str
        Human-readable description of why validation failed.
    severity : str
        Problem severity. Defaults to ``"error"``. Non-error
        severities (e.g. ``"warning"``) do not block acceptance.
    """

    gate_name: str
    entry_path: str | None = None
    reason: str
    severity: str = "error"


class ValidationReport(BaseModel):
    """Outcome of a batch-validation pass.

    Parameters
    ----------
    ok : bool
        ``True`` when no blocking (``severity == "error"``) problems
        were found.
    problems : list[ValidationProblem]
        All problems discovered during validation. Empty when the
        batch is fully valid.
    """

    ok: bool
    problems: list[ValidationProblem] = Field(default_factory=list)
