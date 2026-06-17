from __future__ import annotations

from typing import Callable

from anvil.services.compute.errors import ComputeBackendUnavailable
from anvil.services.compute.protocol import ComputeBackendProtocol

_BackendFactory = Callable[..., ComputeBackendProtocol]

_registry: dict[str, _BackendFactory] = {}


def register(name: str, factory: _BackendFactory) -> None:
    _registry[name] = factory


def get_backend(name: str, **deps: object) -> ComputeBackendProtocol:
    factory = _registry.get(name)
    if factory is None:
        raise ComputeBackendUnavailable(
            f"Compute backend {name!r} is not registered"
        )
    return factory(**deps)


def available_backends() -> list[dict[str, object]]:
    results: list[dict[str, object]] = []
    for name, factory in _registry.items():
        try:
            backend = factory()
            available = backend.is_available()
            reason: str | None = None
        except Exception:
            available = False
            reason = "failed to initialise"
        results.append({
            "value": name,
            "label": _label_for(name),
            "available": available,
            "reason": reason,
        })
    return results


def _label_for(name: str) -> str:
    labels = {
        "auto": "Auto",
        "local-cpu": "Local (CPU)",
        "local-gpu": "Local (GPU)",
        "modal": "Modal (cloud GPU)",
    }
    return labels.get(name, name)