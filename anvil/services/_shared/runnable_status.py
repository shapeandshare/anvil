# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Runnable status enumeration for external model execution eligibility."""

from __future__ import annotations

from enum import StrEnum


class RunnableStatus(StrEnum):
    """Whether an external model is eligible for local execution.

    Attributes
    ----------
    RUNNABLE : str
        Model is eligible for fine-tune and inference (``"runnable"``).
    TRACK_ONLY : str
        Model is metadata-only; cannot be executed (``"track_only"``).
    """

    RUNNABLE = "runnable"
    TRACK_ONLY = "track_only"