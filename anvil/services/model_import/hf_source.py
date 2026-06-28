# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""HuggingFace Hub ``ModelSource`` implementation."""

from __future__ import annotations

import asyncio
import os
from typing import TYPE_CHECKING

from .._shared.import_types import ModelMetadata, ModelSourceError

if TYPE_CHECKING:
    from huggingface_hub.hf_api import ModelInfo


class HfHubSource:
    """Resolve model metadata from the HuggingFace Hub API.

    Requires the ``finetune`` extra (``huggingface_hub``).  The import
    of ``huggingface_hub`` is guarded by ``try/except ImportError`` per
    the optional-dependency pattern in ``resolve.py`` / ``_torch_available()``.

    Attributes
    ----------
    name : str
        Human-readable source identifier (``"huggingface"``).
    """

    name = "huggingface"

    def __init__(self) -> None:
        self._available = _huggingface_hub_available()

    async def resolve_metadata(
        self,
        identifier: str,
        *,
        revision: str = "main",
        token: str | None = None,
    ) -> ModelMetadata:
        """Resolve model metadata from the HuggingFace Hub.

        Parameters
        ----------
        identifier : str
            HF repo ID (e.g. ``"TinyLlama/TinyLlama-1.1B-Chat-v1.0"``).
        revision : str
            Branch, tag, or commit SHA. Defaults to ``"main"``.
        token : str | None
            HF Hub API token. Falls back to ``HF_TOKEN`` env var.

        Returns
        -------
        ModelMetadata
            Resolved metadata from the model card and Hub API.

        Raises
        ------
        ModelSourceError
            If resolution fails (network, auth, rate-limit, not-found,
            parse-failure, or missing extra).
        """
        if not self._available:
            raise ModelSourceError(
                code="missing_extra",
                message="Install anvil[finetune] to import from HuggingFace Hub",
                source=self.name,
            )

        effective_token = token or os.environ.get("HF_TOKEN")
        return await _do_resolve(identifier, revision, effective_token)


def _huggingface_hub_available() -> bool:
    """Check whether the ``huggingface_hub`` package is installed."""
    try:
        import huggingface_hub  # noqa: F401

        return True
    except ImportError:
        return False


async def _do_resolve(
    identifier: str, revision: str, token: str | None
) -> ModelMetadata:
    """Perform the actual HF Hub API call (separated for testability)."""
    try:
        from huggingface_hub import HfApi
    except ImportError:
        raise ModelSourceError(
            code="missing_extra",
            message="Install anvil[finetune] to import from HuggingFace Hub",
            source="huggingface",
        ) from None

    api = HfApi(token=token)

    def _get_info() -> ModelInfo:
        return api.model_info(identifier, revision=revision)

    try:
        loop = asyncio.get_event_loop()
        info = await loop.run_in_executor(None, _get_info)
    except Exception as exc:
        exc_name = type(exc).__name__
        exc_str = str(exc)

        if "404" in exc_str or "not found" in exc_str.lower():
            raise ModelSourceError(
                code="not_found",
                message=f"Model not found: {identifier} @ {revision}",
                source="huggingface",
            ) from exc
        if "401" in exc_str or "403" in exc_str or "authorization" in exc_str.lower():
            raise ModelSourceError(
                code="auth_required",
                message=f"Gated model requires HF_TOKEN: {identifier}",
                source="huggingface",
            ) from exc
        if "429" in exc_str or "rate" in exc_str.lower():
            raise ModelSourceError(
                code="rate_limited",
                message="HF Hub API rate limit exceeded",
                source="huggingface",
            ) from exc
        if "connection" in exc_str.lower() or "timeout" in exc_str.lower():
            raise ModelSourceError(
                code="network_error",
                message=f"Network error contacting HF Hub: {exc_str[:100]}",
                source="huggingface",
            ) from exc

        raise ModelSourceError(
            code="parse_failure",
            message=f"HF Hub API error ({exc_name}): {exc_str[:200]}",
            source="huggingface",
        ) from exc

    # Extract metadata from model info response.
    safetensors = info.safetensors
    param_count = (
        sum(safetensors.parameters.values())
        if safetensors and safetensors.parameters
        else 0
    )

    config = info.config or {}
    arch = config.get("architectures", [None])[0] if isinstance(config, dict) else None
    arch_family = str(arch or info.pipeline_tag or "unknown")

    return ModelMetadata(
        display_name=info.id or identifier,
        architecture_family=arch_family,
        parameter_count=param_count or 0,
        license=(
            getattr(info, "cardData", {}).get("license", "unknown")
            if hasattr(info, "cardData")
            else "unknown"
        ),
        tokenizer_family=(
            info.config.get("tokenizer_config", {}).get("tokenizer_class", "unknown")
            if isinstance(info.config, dict)
            else "unknown"
        ),
        revision_sha=info.sha or revision,
        config_json=str(info.config) if info.config is not None else None,
    )
