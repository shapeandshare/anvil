# Copyright © 2026 Josh Burt
# one-class:allow — intentional domain grouping of tightly coupled dataset schemas
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Request body models for dataset management endpoints.

Pure Pydantic ``BaseModel`` subclasses used as request bodies for
dataset management endpoints.  No business logic -- validation only.
"""

from __future__ import annotations

from pydantic import BaseModel


class CreateDatasetBody(BaseModel):
    """Request body for creating a new dataset.

    Parameters
    ----------
    name : str
        The dataset name.
    description : str | None, optional
        Optional description. Defaults to ``None``.
    """

    name: str
    description: str | None = None


class UpdateDatasetBody(BaseModel):
    """Request body for updating an existing dataset.

    Parameters
    ----------
    name : str | None, optional
        New dataset name. Defaults to ``None``.
    description : str | None, optional
        New description. Defaults to ``None``.
    """

    name: str | None = None
    description: str | None = None


class ImportBody(BaseModel):
    """Request body for importing text into a dataset.

    Parameters
    ----------
    format : str
        Import format (e.g. ``"txt"``, ``"csv"``, ``"jsonl"``).
    text : str
        Raw text content to import.
    """

    format: str
    text: str


class FilterBody(BaseModel):
    """Request body for filtering dataset samples by length.

    Parameters
    ----------
    min_length : int | None, optional
        Minimum sample length in characters. Defaults to ``None``.
    max_length : int | None, optional
        Maximum sample length in characters. Defaults to ``None``.
    """

    min_length: int | None = None
    max_length: int | None = None


class ReplaceBody(BaseModel):
    """Request body for regex replacement across dataset samples.

    Parameters
    ----------
    pattern : str
        Regex pattern to match.
    replacement : str
        Replacement string.
    case_sensitive : bool, optional
        Whether the regex is case-sensitive. Defaults to ``True``.
    """

    pattern: str
    replacement: str
    case_sensitive: bool = True


class UpdateSampleBody(BaseModel):
    """Request body for updating a single dataset sample.

    Parameters
    ----------
    text : str
        New text content for the sample.
    """

    text: str


class CloneDatasetBody(BaseModel):
    """Request body for cloning an existing dataset.

    Parameters
    ----------
    name : str
        Name for the new cloned dataset.
    description : str | None, optional
        Optional description. Defaults to ``None``.
    """

    name: str
    description: str | None = None


class CreateFromCorpusBody(BaseModel):
    """Request body for creating a dataset from a corpus with chunking.

    Parameters
    ----------
    corpus_id : int
        The source corpus ID.
    name : str
        Name for the new dataset.
    description : str | None, optional
        Optional description. Defaults to ``None``.
    chunking_strategy : str, optional
        Chunking strategy (``"windowed"``, ``"file"``, or ``"line"``).
        Defaults to ``"windowed"``.
    block_size : int | None, optional
        Block size for windowed chunking. Required when strategy is
        ``"windowed"``. Defaults to ``None``.
    chunk_overlap : float, optional
        Overlap fraction for windowed chunking. Defaults to ``0.25``.
    """

    corpus_id: int
    name: str
    description: str | None = None
    chunking_strategy: str = "windowed"
    block_size: int | None = None
    chunk_overlap: float = 0.25
