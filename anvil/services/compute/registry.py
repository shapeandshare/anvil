"""Compute backend registry.

Provides a lightweight plugin-style registry for compute backends.
Backends auto-register at module import time via the ``register()``
function, and consumers look up backends by name via ``get_backend()``
or enumerate available options via ``available_backends()``.

The registry pattern decouples backend discovery from resolution:
backends declare themselves and the resolution layer (see ``resolve.py``)
maps user-facing config strings to concrete backends.
"""

from collections.abc import Callable

from .compute_backend import ComputeBackend
from .compute_backend_unavailable import ComputeBackendUnavailable
from .protocol import ComputeBackendProtocol

#: Type alias for factory callables that instantiate compute backends.
#: Factories accept keyword arguments (dependency injection) and return
#: a ``ComputeBackendProtocol`` instance.
_BackendFactory = Callable[..., ComputeBackendProtocol]

#: Internal mapping of registered backend names to their factory functions.
_registry: dict[str, _BackendFactory] = {}


def register(name: str, factory: _BackendFactory) -> None:
    """Register a compute backend under the given name.

    Called by backend modules at import time (e.g. ``local.py`` and
    ``modal_backend.py``) to make themselves available to the resolution
    layer.  Subsequent calls with the same ``name`` overwrite the prior
    entry.

    Parameters
    ----------
    name : str
        Unique identifier for the backend (e.g. ``"local-stdlib"``,
        ``"modal"``).
    factory : _BackendFactory
        Callable that returns a ``ComputeBackendProtocol`` instance when
        invoked.  May accept keyword arguments for dependency injection.
    """
    _registry[name] = factory


def get_backend(name: str, **deps: object) -> ComputeBackendProtocol:
    """Retrieve a registered backend instance by name.

    Looks up the factory registered under ``name``, instantiates it with
    the provided keyword dependencies, and returns the resulting backend.

    Parameters
    ----------
    name : str
        Backend identifier to look up (must have been previously
        registered via ``register()``).
    **deps : object
        Additional keyword arguments forwarded to the factory callable
        for dependency injection.

    Returns
    -------
    ComputeBackendProtocol
        Instantiated compute backend ready for use.

    Raises
    ------
    ComputeBackendUnavailable
        If ``name`` has not been registered.
    """
    factory = _registry.get(name)
    if factory is None:
        raise ComputeBackendUnavailable(f"Compute backend {name!r} is not registered")
    return factory(**deps)


def available_backends() -> list[dict[str, object]]:
    """Enumerate all registered backends with availability status.

    Iterates every entry in the registry, attempts to instantiate each
    backend, and queries ``is_available()``.  Backends that fail to
    initialise are marked as unavailable with an explanatory reason.

    Returns
    -------
    list[dict[str, object]]
        List of dictionaries, each containing:
        - ``value`` : str -- backend identifier
        - ``label`` : str -- human-readable display label
        - ``available`` : bool -- whether the backend is usable
        - ``reason`` : str | None -- reason for unavailability, if any
    """
    results: list[dict[str, object]] = []
    for name, factory in _registry.items():
        try:
            backend = factory()
            available = backend.is_available()
            reason: str | None = None
        except Exception:
            available = False
            reason = "failed to initialise"
        results.append(
            {
                "value": name,
                "label": _label_for(name),
                "available": available,
                "reason": reason,
            }
        )
    return results


def _label_for(name: str) -> str:
    """Map a ``ComputeBackend`` identifier to a human-readable display label.

    Parameters
    ----------
    name : str
        ``ComputeBackend`` identifier (e.g. ``ComputeBackend.LOCAL_CPU``,
        ``ComputeBackend.MODAL``).

    Returns
    -------
    str
        Human-readable label, or the raw ``name`` if no mapping exists.
    """
    labels = {
        ComputeBackend.AUTO: "Auto",
        ComputeBackend.LOCAL_CPU: "Local (CPU)",
        ComputeBackend.LOCAL_GPU: "Local (GPU)",
        ComputeBackend.MODAL: "Modal (cloud GPU)",
    }
    return labels.get(name, name)
