# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Shared types for the model-import domain.

Enumerations, data transfer objects, and exception types shared
across the model-import service, API, CLI, and SDK layers.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel


class SourceType(StrEnum):
    """Origin source of an external model.

    Attributes
    ----------
    HUGGINGFACE : str
        HuggingFace Hub repository (``"huggingface"``).
    LOCAL : str
        Local file or directory path (``"local"``).
    """

    HUGGINGFACE = "huggingface"
    LOCAL = "local"


class RunnableStatus(StrEnum):
    """Whether an external model is eligible for local execution.

    Attributes
    ----------
    RUNNABLE : str
        Model is eligible for fine-tune and inference (``"runnable"``).
    TRACK_ONLY : str
        Model is metadata-only; cannot be executed (``"track_only"``).
    """

    RUNNABLE = "runnable"
    TRACK_ONLY = "track_only"


class AssetState(StrEnum):
    """Availability of a model's downloaded assets.

    Attributes
    ----------
    METADATA_ONLY : str
        No assets downloaded; only metadata exists (``"metadata_only"``).
    ASSETS_AVAILABLE : str
        Weights, tokenizer, and config have been downloaded (``"assets_available"``).
    ASSETS_PENDING : str
        Asset download is in progress (``"assets_pending"``).
    """

    METADATA_ONLY = "metadata_only"
    ASSETS_AVAILABLE = "assets_available"
    ASSETS_PENDING = "assets_pending"


class ModelImportJobStatus(StrEnum):
    """Lifecycle state of an asynchronous model-import job.

    Attributes
    ----------
    QUEUED : str
        Job created; not yet started (``"queued"``).
    RESOLVING : str
        Metadata resolution is in progress (``"resolving"``).
    COMPLETE : str
        Metadata resolved and ``ExternalModel`` entry created (``"complete"``).
    FAILED : str
        Resolution failed with a typed error code (``"failed"``).
    """

    QUEUED = "queued"
    RESOLVING = "resolving"
    COMPLETE = "complete"
    FAILED = "failed"


class ModelMetadata(BaseModel):
    """Resolved metadata fields from a ``ModelSource``.

    Parameters
    ----------
    display_name : str
        Human-readable model name.
    architecture_family : str
        Model architecture identifier (e.g., ``"LlamaForCausalLM"``).
    parameter_count : int
        Total number of parameters.
    license : str
        SPDX license identifier or ``"unknown"``.
    tokenizer_family : str
        Tokenizer type (e.g., ``"sentencepiece"``, ``"tokenizers"``).
    revision_sha : str
        Source revision or commit SHA.
    config_json : str | None
        Raw model configuration as JSON text, if available.
    """

    display_name: str
    architecture_family: str
    parameter_count: int
    license: str
    tokenizer_family: str
    revision_sha: str
    config_json: str | None = None


class ModelSourceError(Exception):
    """Raised when a ``ModelSource`` fails to resolve metadata.

    Parameters
    ----------
    code : str
        Typed error code (``network_error``, ``auth_required``,
        ``rate_limited``, ``not_found``, ``invalid_identifier``,
        ``parse_failure``).
    message : str
        Human-readable error description.
    source : str
        Source type identifier (``"huggingface"`` or ``"local"``).
    """

    def __init__(self, code: str, message: str, source: str) -> None:
        self.code = code
        self.message = message
        self.source = source
        super().__init__(f"[{code}] {message} (source={source})")
