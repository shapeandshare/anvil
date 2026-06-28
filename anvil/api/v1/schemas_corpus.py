# Copyright © 2026 Josh Burt
# one-class:allow — intentional domain grouping of tightly coupled corpus schemas
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Request body models for corpus management API endpoints.

Pure Pydantic ``BaseModel`` subclasses used for creating, forking,
resolving, and analyzing corpora.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class CreateCorpusBody(BaseModel):
    """Request body for creating a new corpus from a directory path.

    Parameters
    ----------
    name : str
        The corpus name. Must be 1-255 characters.
    root_path : str
        Filesystem path to scan. Must be 1-255 characters.
    include_patterns : list[str] | None, optional
        Gitignore-style include patterns. Defaults to ``None``.
    exclude_patterns : list[str] | None, optional
        Gitignore-style exclude patterns. Defaults to ``None``.
    description : str | None, optional
        Optional description. Defaults to ``None``.
    chunking_strategy : str, optional
        Chunking algorithm (``"windowed"``, ``"file"``, or ``"line"``).
        Defaults to ``"windowed"``.
    chunk_overlap : float, optional
        Fractional overlap between chunks. Defaults to ``0.5``.
    block_size : int, optional
        Token block size for windowed chunking. Defaults to ``16``.
    """

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=255)
    root_path: str = Field(min_length=1, max_length=255)
    include_patterns: list[str] | None = None
    exclude_patterns: list[str] | None = None
    description: str | None = None
    chunking_strategy: str = "windowed"
    chunk_overlap: float = 0.5
    block_size: int = 16


class ForkCorpusBody(BaseModel):
    """Request body for forking an existing corpus.

    Parameters
    ----------
    name : str
        New corpus name. Must be 1-255 characters.
    include_patterns : list[str] | None, optional
        Gitignore-style include patterns. Defaults to ``None``.
    exclude_patterns : list[str] | None, optional
        Gitignore-style exclude patterns. Defaults to ``None``.
    description : str | None, optional
        Optional description. Defaults to ``None``.
    chunking_strategy : str | None, optional
        Chunking strategy override. Defaults to ``None``.
    chunk_overlap : float | None, optional
        Overlap override. Defaults to ``None``.
    block_size : int | None, optional
        Block size override. Defaults to ``None``.
    """

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=255)
    include_patterns: list[str] | None = None
    exclude_patterns: list[str] | None = None
    description: str | None = None
    chunking_strategy: str | None = None
    chunk_overlap: float | None = None
    block_size: int | None = None


class ResolvePathBody(BaseModel):
    """Request body for resolving a folder name to an absolute path.

    Parameters
    ----------
    folder_name : str
        The folder name to locate. Must be 1-255 characters.
    """

    model_config = ConfigDict(extra="forbid")

    folder_name: str = Field(min_length=1, max_length=255)


class AnalyzePathBody(BaseModel):
    """Request body for analyzing a directory path.

    Parameters
    ----------
    path : str
        Directory path to analyze. Must be 1-255 characters.
    include_patterns : list[str] | None, optional
        Gitignore-style include patterns. Defaults to ``None``.
    exclude_patterns : list[str] | None, optional
        Gitignore-style exclude patterns. Defaults to ``None``.
    """

    model_config = ConfigDict(extra="forbid")

    path: str = Field(min_length=1, max_length=255)
    include_patterns: list[str] | None = None
    exclude_patterns: list[str] | None = None
