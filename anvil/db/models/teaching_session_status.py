# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Teaching session status enumeration."""

from __future__ import annotations

from enum import StrEnum


class TeachingSessionStatus(StrEnum):
    """Lifecycle status of a ``TeachingSession``.

    Attributes
    ----------
    DRAFT : str
        Session created; base selected or none; no completed rounds (``"draft"``).
    ACTIVE : str
        At least one round finalized; chain head is ``current_base_experiment_id``
        on the session row (``"active"``).
    COMPLETED : str
        Learner marked session done; read-only (``"completed"``).
    """

    DRAFT = "draft"
    ACTIVE = "active"
    COMPLETED = "completed"
