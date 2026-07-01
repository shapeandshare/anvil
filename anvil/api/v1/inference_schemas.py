# one-class:allow — tightly coupled Pydantic request body schemas for the same inference router
# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Pydantic request body schemas for inference endpoints.

All 7 classes are defined here (tightly coupled Pydantic request bodies
for the same inference router), extracted from ``inference.py`` to satisfy
the one-class-per-file rule.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class InferenceTokenizeBody(BaseModel):
    """Request body for the tokenization endpoint.

    Parameters
    ----------
    text : str
        Text to tokenize. Must be between 1 and 100 000 characters.
    model_id : str | None, optional
        Model identifier. Defaults to ``None``.
    version : int | None, optional
        Model version. Defaults to ``None``.
    """

    text: str = Field(min_length=1, max_length=100_000)
    model_id: int | None = None
    version: int | None = None
    model_config = ConfigDict(extra="forbid")


class InferenceEmbeddingsBody(BaseModel):
    """Request body for the embeddings endpoint.

    Parameters
    ----------
    text : str
        Text to embed. Must be between 1 and 10 000 characters.
    model_id : str | None, optional
        Model identifier. Defaults to ``None``.
    version : int | None, optional
        Model version. Defaults to ``None``.
    """

    text: str = Field(min_length=1, max_length=10_000)
    model_id: int | None = None
    version: int | None = None
    model_config = ConfigDict(extra="forbid")


class InferenceAttentionBody(BaseModel):
    """Request body for the attention endpoint.

    Parameters
    ----------
    text : str
        Input text. Must be between 1 and 100 000 characters.
    model_id : str | None, optional
        Model identifier. Defaults to ``None``.
    version : int | None, optional
        Model version. Defaults to ``None``.
    """

    text: str = Field(min_length=1, max_length=100_000)
    model_id: int | None = None
    version: int | None = None
    model_config = ConfigDict(extra="forbid")


class InferenceSamplingBody(BaseModel):
    """Request body for the sampling distribution endpoint.

    Parameters
    ----------
    prompt : str
        Prompt text.
    temperature : float, optional
        Sampling temperature. Must be positive. Defaults to ``0.5``.
    top_k : int | None, optional
        Top-k filtering value. Defaults to ``None``.
    model_id : str | None, optional
        Model identifier. Defaults to ``None``.
    version : int | None, optional
        Model version. Defaults to ``None``.
    """

    prompt: str = ""
    temperature: float = Field(default=0.5, gt=0)
    top_k: int | None = None
    model_id: int | None = None
    version: int | None = None
    model_config = ConfigDict(extra="forbid")


class InferenceBackwardBody(BaseModel):
    """Request body for the backward graph endpoint.

    Parameters
    ----------
    text : str
        Input text. Must be between 1 and 100 000 characters.
    model_id : str | None, optional
        Model identifier. Defaults to ``None``.
    version : int | None, optional
        Model version. Defaults to ``None``.
    """

    text: str = Field(min_length=1, max_length=100_000)
    model_id: int | None = None
    version: int | None = None
    model_config = ConfigDict(extra="forbid")


class InferenceAutogradBody(BaseModel):
    """Request body for the autograd example endpoint.

    Parameters
    ----------
    text : str
        Input text. Must be between 1 and 100 000 characters.
    model_id : str | None, optional
        Model identifier. Defaults to ``None``.
    version : int | None, optional
        Model version. Defaults to ``None``.
    """

    text: str = Field(min_length=1, max_length=100_000)
    model_id: int | None = None
    version: int | None = None
    model_config = ConfigDict(extra="forbid")


class InferenceLossBody(BaseModel):
    """Request body for the loss-breakdown endpoint.

    Parameters
    ----------
    text : str
        Input text for loss computation.
    model_id : int | None, optional
        Model identifier.
    version : int | None, optional
        Model version.
    """

    text: str = Field(min_length=1, max_length=10_000)
    model_id: int | None = None
    version: int | None = None
    model_config = ConfigDict(extra="forbid")


class InferenceGenerateBody(BaseModel):
    """Request body for the text-generation endpoint.

    Parameters
    ----------
    model_id : int
        Model identifier.
    prompt : str
        Input prompt for generation.
    adapter_id : str | None, optional
        LoRA adapter identifier (e.g. ``"run_42"``). When provided,
        generation composes base weights + adapter. When absent,
        base-only generation is used.
    temperature : float, optional
        Sampling temperature. Default ``0.7``.
    max_tokens : int, optional
        Maximum tokens to generate. Default ``100``.
    """

    model_id: int
    prompt: str = Field(min_length=1, max_length=10_000)
    adapter_id: str | None = None
    temperature: float = Field(default=0.7, ge=0, le=2.0)
    max_tokens: int = Field(default=100, ge=1, le=2048)
    model_config = ConfigDict(extra="forbid")
