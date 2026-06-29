# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Caching HTTP client for the HuggingFace Hub search/list APIs.

Requires the ``finetune`` extra (``huggingface_hub``).  The import of
``huggingface_hub`` is performed lazily inside ``__init__`` — callers
must guard instantiation against the optional extra themselves.
"""

from __future__ import annotations

import time
from typing import Any

try:
    from huggingface_hub import HfApi  # finetune extra
except ImportError:
    HfApi = None


class HubClient:
    """Wraps ``huggingface_hub.HfApi`` with in-memory TTL caching.

    Provides two public methods — ``search_models`` and ``get_model_info`` —
    that cache results in memory for a configurable TTL.  The underlying
    ``HfApi`` import is deferred to ``__init__`` so that this module can
    be imported without the ``finetune`` extra (instantiation will fail if
    ``huggingface_hub`` is not installed).

    Parameters
    ----------
    token : str | None
        HuggingFace Hub API token.  Passed through to ``HfApi``; many
        public models do not require one, but gated models do.
    """

    def __init__(self, token: str | None = None) -> None:
        if HfApi is None:
            msg = (
                "huggingface_hub is required. "
                "Install with: pip install anvil[finetune]"
            )
            raise RuntimeError(msg)
        self._api = HfApi(token=token)

        # Search cache: key -> (timestamp, results_list)
        self._search_cache: dict[str, tuple[float, object]] = {}
        # Model-info cache: hf_id -> (timestamp, serialized_dict)
        self._info_cache: dict[str, tuple[float, dict[str, Any]]] = {}

        self._search_ttl: int = 300  # 5 minutes
        self._info_ttl: int = 1800  # 30 minutes

    ########################################################################
    # Public API
    ########################################################################

    def search_models(self, query: str, limit: int = 20) -> dict[str, Any]:
        """Search models on HuggingFace Hub with TTL caching.

        Parameters
        ----------
        query : str
            Search string passed to ``HfApi.list_models(search=...)``.
        limit : int
            Maximum number of results to return.  Defaults to 20.

        Returns
        -------
        dict
            A result dict with keys:
            - ``results`` (list[dict]): serialized model records
            - ``cached`` (bool): whether the result came from cache
            - ``error`` (str | None): error message, or ``None`` on success
        """
        cache_key = f"{query}:{limit}"

        # Check cache for a fresh hit first.
        cached = self._search_cache.get(cache_key)
        if cached is not None and not self._is_expired(cached[0], self._search_ttl):
            return {"results": cached[1], "cached": True, "error": None}

        try:
            raw = list(self._api.list_models(search=query))
            results = _serialize_models(raw, limit)
            self._search_cache[cache_key] = (time.time(), results)
            return {"results": results, "cached": False, "error": None}

        except Exception as exc:
            exc_str = str(exc)
            # 429 rate-limit — serve stale cache if available.
            if "429" in exc_str:
                if cached is not None:
                    return {"results": cached[1], "cached": True, "error": None}
                return {
                    "results": [],
                    "cached": False,
                    "error": "Rate limited. Retry in N seconds.",
                }
            return {"results": [], "cached": False, "error": exc_str}

    def get_model_info(self, hf_id: str) -> dict[str, Any] | None:
        """Fetch metadata for a single model by HF repo ID.

        Parameters
        ----------
        hf_id : str
            HuggingFace repo ID (e.g. ``"TinyLlama/TinyLlama-1.1B-Chat-v1.0"``).

        Returns
        -------
        dict | None
            Serialized model info dict, or ``None`` if the model is not
            found or an error occurs.  On error, stale cached data is
            returned if available.
        """
        # Return fresh cache hit immediately.
        cached = self._info_cache.get(hf_id)
        if cached is not None and not self._is_expired(cached[0], self._info_ttl):
            return cached[1]

        try:
            info = self._api.model_info(hf_id)
            serialized = _serialize_model_info(info)
            self._info_cache[hf_id] = (time.time(), serialized)
            return serialized

        except Exception:
            # Return stale cache on any error, or None.
            if cached is not None:
                return cached[1]
            return None

    ########################################################################
    # Internal helpers
    ########################################################################

    @staticmethod
    def _is_expired(timestamp: float, ttl: int) -> bool:
        """Check whether a cached entry has exceeded its TTL.

        Parameters
        ----------
        timestamp : float
            ``time.time()`` value when the entry was cached.
        ttl : int
            Time-to-live in seconds.

        Returns
        -------
        bool
            ``True`` if the entry has expired.
        """
        return time.time() - timestamp > ttl


def _serialize_models(models: list[Any], limit: int) -> list[dict[str, Any]]:
    """Convert a list of ``ModelInfo`` objects to plain dicts.

    Parameters
    ----------
    models : list[ModelInfo]
        Results from ``HfApi.list_models()``.
    limit : int
        Maximum number of models to include.

    Returns
    -------
    list[dict]
        Serialized model records with keys ``hf_id``, ``display_name``,
        ``params``, ``license``, ``architecture``, ``is_curated``.
    """
    results: list[dict[str, Any]] = []
    for m in models[:limit]:
        card_data = _safe_get(m, "cardData", {})
        config = _safe_get(m, "config")
        safetensors = _safe_get(m, "safetensors")

        params: int = 0
        if (
            safetensors
            and hasattr(safetensors, "parameters")
            and safetensors.parameters
        ):
            params = sum(safetensors.parameters.values())

        architecture: str = "unknown"
        if isinstance(config, dict):
            arch_list = config.get("architectures", [])
            architecture = str(arch_list[0]) if arch_list else "unknown"

        results.append(
            {
                "hf_id": m.modelId,
                "display_name": m.modelId,
                "params": params,
                "license": (
                    card_data.get("license", "unknown")
                    if isinstance(card_data, dict)
                    else "unknown"
                ),
                "architecture": architecture,
                "is_curated": False,
            }
        )
    return results


def _serialize_model_info(info: Any) -> dict[str, Any]:
    """Convert a single ``ModelInfo`` object to a plain dict.

    Parameters
    ----------
    info : ModelInfo
        Result from ``HfApi.model_info()``.

    Returns
    -------
    dict
        Serialized model info with keys ``hf_id``, ``display_name``,
        ``params``, ``license``, ``architecture``, ``pipeline_tag``,
        ``library_name``, ``downloads``, ``is_curated``.
    """
    card_data = _safe_get(info, "cardData", {})
    config = _safe_get(info, "config")
    safetensors = _safe_get(info, "safetensors")

    params: int = 0
    if safetensors and hasattr(safetensors, "parameters") and safetensors.parameters:
        params = sum(safetensors.parameters.values())

    architecture: str = "unknown"
    if isinstance(config, dict):
        arch_list = config.get("architectures", [])
        architecture = str(arch_list[0]) if arch_list else "unknown"

    return {
        "hf_id": info.modelId,
        "display_name": info.modelId,
        "params": params,
        "license": (
            card_data.get("license", "unknown")
            if isinstance(card_data, dict)
            else "unknown"
        ),
        "architecture": architecture,
        "pipeline_tag": getattr(info, "pipeline_tag", None),
        "library_name": getattr(info, "library_name", None),
        "downloads": getattr(info, "downloads", 0),
        "is_curated": False,
    }


def _safe_get(obj: Any, attr: str, default: Any = None) -> Any:
    """Safely get an attribute from an object without raising.

    Parameters
    ----------
    obj : object
        Any Python object.
    attr : str
        Attribute name.
    default : object
        Value returned when the attribute does not exist.  Defaults to ``None``.

    Returns
    -------
    object
        The attribute value, or *default*.
    """
    return getattr(obj, attr, default)
