# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Event bus abstraction for real-time training metrics.

Decouples compute pods (producers) from web server SSE handlers
(consumers) so they can run in separate processes or containers.
Redis is delivery-only — never the source of truth (AD-4).
"""

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from typing import Any


class EventBus(ABC):
    """Publish/subscribe for streaming events (training metrics).

    In SaaS mode backed by Redis pub/sub. In local mode backed by
    an in-process ``asyncio.Queue``. Both support the same interface
    so the code path is identical.
    """

    @abstractmethod
    async def publish(self, channel: str, event: dict[str, Any]) -> None:
        """Publish an event to *channel*.

        Parameters
        ----------
        channel : str
            Channel name (e.g. ``"training:metrics:{job_id}"``).
        event : dict
            JSON-serialisable event payload with ``event`` and ``data`` keys.
            For metrics: ``{"event": "metrics", "data": {"step": 42, "loss": 1.23}}``.
            For server-signaled degradation: ``{"event": "degraded", "data": {}}`` (FR-045r).
        """

    @abstractmethod
    async def subscribe(self, channel: str) -> AsyncIterator[dict[str, Any]]:
        """Subscribe to events on *channel*, yielding them as they arrive.

        The generator MUST clean up (unsubscribe) on exit or cancellation.

        In SaaS mode, the SSE handler subscribes on a per-connection basis
        (AD-5). On Redis drop, the server sends ``event: degraded`` to
        trigger the client polling fallback (FR-045r).
        """

    @abstractmethod
    async def close(self) -> None:
        """Release all resources (connections, threads)."""


# Implementations:
# - InProcessEventBus: wraps asyncio.Queue (in anvil/storage/)
# - RedisEventBus: redis.asyncio pub/sub (in anvil/_saas/implementations/)
