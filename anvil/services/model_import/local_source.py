# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Local file ``ModelSource`` implementation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import anyio

from .._shared.import_types import ModelMetadata, ModelSourceError


class LocalSource:
    """Resolve model metadata from a local directory.

    Reads ``config.json``, tokenizer metadata, and model card files
    from the given local path.  No optional dependencies required.

    Attributes
    ----------
    name : str
        Human-readable source identifier (``"local"``).
    """

    name = "local"

    async def resolve_metadata(
        self,
        identifier: str,
        *,
        revision: str = "main",
        token: str | None = None,
    ) -> ModelMetadata:
        """Resolve model metadata from a local filesystem path.

        Parameters
        ----------
        identifier : str
            Path to the local model directory.
        revision : str
            Ignored for local sources.
        token : str | None
            Ignored for local sources.

        Returns
        -------
        ModelMetadata
            Extracted metadata from ``config.json`` and related files.

        Raises
        ------
        ModelSourceError
            If the path does not exist or ``config.json`` cannot be parsed.
        """
        model_dir = anyio.Path(identifier)

        if not await model_dir.exists():
            raise ModelSourceError(
                code="not_found",
                message=f"Local path not found: {identifier}",
                source=self.name,
            )
        if not await model_dir.is_dir():
            raise ModelSourceError(
                code="invalid_identifier",
                message=f"Not a directory: {identifier}",
                source=self.name,
            )

        config_path = model_dir / "config.json"
        if not await config_path.exists():
            raise ModelSourceError(
                code="parse_failure",
                message=f"No config.json found in {identifier}",
                source=self.name,
            )

        try:
            raw = await config_path.read_text(encoding="utf-8")
            config = json.loads(raw)
        except (json.JSONDecodeError, OSError) as exc:
            raise ModelSourceError(
                code="parse_failure",
                message=f"Failed to parse config.json: {exc}",
                source=self.name,
            ) from exc

        tokenizer_family = "unknown"
        tok_config_path = model_dir / "tokenizer_config.json"
        if await tok_config_path.exists():
            try:
                tok_raw = await tok_config_path.read_text(encoding="utf-8")
                tok_config = json.loads(tok_raw)
                tokenizer_family = tok_config.get("tokenizer_class", "unknown")
            except (json.JSONDecodeError, OSError):
                pass

        license_id = config.get("license", "unknown")

        arch_list = config.get("architectures", [])
        architecture_family = arch_list[0] if arch_list else "unknown"

        param_count = _estimate_params(config)

        display_name = config.get("_name_or_path", Path(identifier).name)

        return ModelMetadata(
            display_name=display_name,
            architecture_family=architecture_family,
            parameter_count=param_count,
            license=license_id,
            tokenizer_family=tokenizer_family,
            revision_sha="local",
            config_json=raw,
        )


def _estimate_params(config: dict[str, Any]) -> int:
    """Roughly estimate parameter count from a HuggingFace config dict.

    Uses ``num_hidden_layers``, ``hidden_size``, ``intermediate_size``,
    and ``vocab_size`` for a Llama-style estimate. Falls back to ``0``
    (unknown) if the required keys are absent.
    """
    n_layer = int(config.get("num_hidden_layers", 0) or 0)
    n_embd = int(config.get("hidden_size", 0) or 0)
    n_inter = int(config.get("intermediate_size", 0) or 0)
    vocab = int(config.get("vocab_size", 0) or 0)

    if n_layer == 0 or n_embd == 0:
        return int(config.get("parameter_count", 0) or 0)

    attn = 4 * n_embd * n_embd
    mlp = 3 * n_embd * n_inter
    embed = vocab * n_embd
    return n_layer * (attn + mlp) + embed
