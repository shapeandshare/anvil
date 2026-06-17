from __future__ import annotations

from typing import Callable, Protocol

from anvil.services.compute.result import ComputeResult

ProgressCallback = Callable[[int, float], None]
StopCheck = Callable[[], bool]


class ComputeBackendProtocol(Protocol):
    """Structural type for compute backends (PEP 544 — not an ABC).

    Any plain class with ``name: str``, ``is_available()``, and
    ``run(...)`` satisfies this protocol. No inheritance required.
    """

    name: str

    def is_available(self) -> bool:
        ...

    async def run(
        self,
        docs: list[str],
        config: dict,
        *,
        progress_callback: ProgressCallback,
        stop_check: StopCheck,
    ) -> ComputeResult:
        ...