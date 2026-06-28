# Copyright © 2026 Josh Burt
# one-class:allow — intentional domain grouping of tightly coupled eval schemas
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Request body models for evaluation API endpoints.

Pure Pydantic ``BaseModel`` subclasses used for perplexity evaluation,
evaluation dataset creation, and record management.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class EvalPerplexityBody(BaseModel):
    """Request body for computing perplexity on a text.

    Parameters
    ----------
    model_id : int
        Identifier of the model.
    version : int
        Version of the model.
    text : str
        Input text to evaluate. Must be non-empty.
    """

    model_config = ConfigDict(extra="forbid")

    model_id: int
    version: int
    text: str = Field(min_length=1)


class CreateEvalDatasetBody(BaseModel):
    """Request body for creating a new evaluation dataset.

    Parameters
    ----------
    name : str
        The dataset name. Must be 1-255 characters.
    tags : dict | None, optional
        Optional metadata tags. Defaults to ``None``.
    """

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=255)
    tags: dict[str, Any] | None = None


class AppendRecordsBody(BaseModel):
    """Request body for appending records to an evaluation dataset.

    Parameters
    ----------
    records : list
        List of evaluation records to append.
    """

    model_config = ConfigDict(extra="forbid")

    records: list[Any]
