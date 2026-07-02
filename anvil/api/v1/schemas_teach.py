"""Pydantic schemas for the interactive teaching loop API.

Request/response body models for all ``/v1/teach`` endpoints.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class CreateSessionBody(BaseModel):
    """Request body for ``POST /teach/sessions``."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=1000)
    seed_experiment_id: int | None = None


class UpdateStatusBody(BaseModel):
    """Request body for ``PATCH /teach/sessions/{id}/status``."""

    model_config = ConfigDict(extra="forbid")

    status: str = Field(..., min_length=1, max_length=16)


class StartRoundBody(BaseModel):
    """Request body for ``POST /teach/sessions/{id}/rounds``."""

    model_config = ConfigDict(extra="forbid")

    examples: list[str] = Field(..., min_length=1)
    training_config: dict[str, Any]


class InspectRoundBody(BaseModel):
    """Request body for round inspection."""

    model_config = ConfigDict(extra="forbid")

    experiment_id: int
    prompts: list[str] = Field(..., min_length=1)
    temperature: float = Field(default=0.7, ge=0, le=2.0)
    max_tokens: int = Field(default=100, ge=1, le=2048)


class CompareRoundsBody(BaseModel):
    """Request body for ``POST /teach/sessions/compare``."""

    model_config = ConfigDict(extra="forbid")

    left_experiment_id: int
    right_experiment_id: int
    prompts: list[str] = Field(..., min_length=1)
    temperature: float = Field(default=0.7, ge=0, le=2.0)
    max_tokens: int = Field(default=100, ge=1, le=2048)


class RollbackBody(BaseModel):
    """Request body for ``POST /teach/sessions/{id}/rollback``."""

    model_config = ConfigDict(extra="forbid")

    target_experiment_id: int