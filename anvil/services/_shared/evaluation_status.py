# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Evaluation run status enumeration."""

from __future__ import annotations

from enum import StrEnum


class EvaluationRunStatus(StrEnum):
    """Lifecycle status of an ``EvaluationRun``.

    Attributes
    ----------
    PENDING : str
        Created but not yet started (``"pending"``).
    RUNNING : str
        Evaluation is in progress and the SSE stream is active (``"running"``).
    COMPLETED : str
        All prompts evaluated and results persisted (``"completed"``).
    FAILED : str
        Evaluation terminated with an unrecoverable error (``"failed"``).
    """

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
