# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Live status of an isolated instance."""

from __future__ import annotations

from enum import StrEnum


class InstanceStatus(StrEnum):
    """Runtime status of an isolated instance.

    The status is **recomputed** from pidfile / process / port probes
    on every read — it is never stored as authoritative truth in the
    registry (avoids stale truth after crashes).
    """

    RUNNING = "running"
    STOPPED = "stopped"
    UNHEALTHY = "unhealthy"
