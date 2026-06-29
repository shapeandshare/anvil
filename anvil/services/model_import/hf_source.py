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


_WEIGHT_EXTENSIONS: frozenset[str] = frozenset({".safetensors"})
"""Accepted weight-file extensions (v1 only — FR-030)."""

_TOKENIZER_PATTERNS: frozenset[str] = frozenset(
    {"tokenizer.json", "tokenizer_config.json"}
)
"""Tokenizer files to download."""

_CONFIG_FILES: frozenset[str] = frozenset({"config.json"})
"""Configuration files to download."""


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

    async def list_asset_files(
        self,
        identifier: str,
        *,
        revision: str = "main",
        token: str | None = None,
    ) -> list[dict[str, str]]:
        """Resolve the list of asset files for a model.

        Returns filenames for config, tokenizer, and safetensors weight
        files grouped by ``asset_type`` (``"config"``, ``"tokenizer"``,
        ``"weights"``).

        Parameters
        ----------
        identifier : str
            HF repo ID.
        revision : str
            Branch, tag, or commit SHA.
        token : str | None
            HF Hub API token.

        Returns
        -------
        list[dict[str, str]]
            Each entry has ``{"asset_type": ..., "filename": ...}``.

        Raises
        ------
        ModelSourceError
            On network/auth/parse failures.
        """
        if not self._available:
            raise ModelSourceError(
                code="missing_extra",
                message="Install anvil[finetune] to import from HuggingFace Hub",
                source=self.name,
            )
        effective_token = token or os.environ.get("HF_TOKEN")
        return await _do_list_files(identifier, revision, effective_token)

    async def download_asset(
        self,
        identifier: str,
        filename: str,
        *,
        revision: str = "main",
        token: str | None = None,
    ) -> bytes:
        """Download a single asset file from the HF Hub.

        Parameters
        ----------
        identifier : str
            HF repo ID.
        filename : str
            Path within the repo (e.g. ``"model.safetensors"``).
        revision : str
            Branch, tag, or commit SHA.
        token : str | None
            HF Hub API token.

        Returns
        -------
        bytes
            The file contents.

        Raises
        ------
        ModelSourceError
            On network/auth/not-found errors.
        """
        if not self._available:
            raise ModelSourceError(
                code="missing_extra",
                message="Install anvil[finetune] to import from HuggingFace Hub",
                source=self.name,
            )
        effective_token = token or os.environ.get("HF_TOKEN")
        return await _do_download(identifier, filename, revision, effective_token)


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


async def _do_list_files(
    identifier: str, revision: str, token: str | None
) -> list[dict[str, str]]:
    """List asset files for a model repo on the HF Hub."""
    try:
        from huggingface_hub import HfApi
    except ImportError:
        raise ModelSourceError(
            code="missing_extra",
            message="Install anvil[finetune] to import from HuggingFace Hub",
            source="huggingface",
        ) from None

    api = HfApi(token=token)

    def _list_all() -> list[str]:
        return list(api.list_repo_files(identifier, revision=revision))

    try:
        loop = asyncio.get_event_loop()
        all_files: list[str] = await loop.run_in_executor(None, _list_all)
    except Exception as exc:
        _raise_hf_error(exc, identifier, revision)
        raise  # unreachable: _raise_hf_error always raises

    assets: list[dict[str, str]] = []

    for fname in all_files:
        if fname in _CONFIG_FILES:
            assets.append({"asset_type": "config", "filename": fname})
        elif fname in _TOKENIZER_PATTERNS:
            assets.append({"asset_type": "tokenizer", "filename": fname})
        elif any(fname.endswith(ext) for ext in _WEIGHT_EXTENSIONS):
            assets.append({"asset_type": "weights", "filename": fname})
        # Silently skip non-asset files (e.g. README.md, .gitattributes)

    return assets


async def _do_download(
    identifier: str,
    filename: str,
    revision: str,
    token: str | None,
) -> bytes:
    """Download a single file from the HF Hub."""
    try:
        from huggingface_hub import hf_hub_download
    except ImportError:
        raise ModelSourceError(
            code="missing_extra",
            message="Install anvil[finetune] to import from HuggingFace Hub",
            source="huggingface",
        ) from None

    import tempfile

    def _download() -> str:
        local_dir = tempfile.mkdtemp(prefix="anvil_hf_")
        return str(
            hf_hub_download(
                repo_id=identifier,
                filename=filename,
                revision=revision,
                token=token,
                local_dir=local_dir,
                local_files_only=False,
            )
        )

    try:
        loop = asyncio.get_event_loop()
        local_path = await loop.run_in_executor(None, _download)
        loop2 = asyncio.get_event_loop()
        data = await loop2.run_in_executor(None, _read_file, local_path)
        return data
    except Exception as exc:
        _raise_hf_error(exc, identifier, revision)
        # unreachable: _raise_hf_error always raises
        raise


def _read_file(path: str) -> bytes:
    """Read a file from disk (run_in_executor helper)."""
    with open(path, "rb") as f:
        return f.read()


def _raise_hf_error(exc: Exception, identifier: str, revision: str) -> None:
    """Translate HF Hub exceptions into typed ``ModelSourceError``.

    Parameters
    ----------
    exc : Exception
        The caught exception from huggingface_hub.
    identifier : str
        HF repo ID (for error messages).
    revision : str
        Source revision (for error messages).

    Raises
    ------
    ModelSourceError
        Always raised with an appropriate error code.
    """
    exc_name = type(exc).__name__
    exc_str = str(exc)

    if "404" in exc_str or "not found" in exc_str.lower():
        raise ModelSourceError(
            code="not_found",
            message=f"File not found: {identifier} @ {revision}",
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
        message=f"HF Hub error ({exc_name}): {exc_str[:200]}",
        source="huggingface",
    ) from exc
