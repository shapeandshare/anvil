# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Feedback report status enumeration."""

from __future__ import annotations

from enum import StrEnum


class FeedbackStatus(StrEnum):
    """Lifecycle status of a ``FeedbackReport``.

    Attributes
    ----------
    OPEN : str
        Report created; awaiting review (``"open"``).
    IN_PROGRESS : str
        Report is being addressed (``"in_progress"``).
    RESOLVED : str
        Report has been resolved; read-only (``"resolved"``).
    """

    OPEN = "open"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
