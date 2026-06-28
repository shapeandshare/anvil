# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""NoteMetadata model — metadata about a vault note collected during scanning."""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class NoteMetadata(BaseModel):
    """Metadata about a vault note collected during scanning.

    Attributes
    ----------
    path : Path
        Absolute filesystem path to the ``.md`` file.
    stem : str
        Filename without extension (NFC-normalized).
    frontmatter : dict
        Raw parsed YAML frontmatter.
    title : str | None
        Frontmatter ``title`` field.
    note_type : str | None
        Frontmatter ``type`` field.
    tags : list[str]
        Frontmatter ``tags`` list.
    created_date : date | None
        Frontmatter ``created`` field.
    updated_date : date | None
        Frontmatter ``updated`` field.
    last_modified : datetime | None
        Filesystem mtime.
    outbound_stems : list[str]
        Wikilink targets extracted from body text.
    inbound_stems : list[str]
        Populated after graph build (notes linking to this note).
    """

    path: Path
    stem: str
    frontmatter: dict[str, Any] = Field(default_factory=dict)
    title: str | None = None
    note_type: str | None = None
    tags: list[str] = Field(default_factory=list)
    created_date: date | None = None
    updated_date: date | None = None
    last_modified: datetime | None = None
    outbound_stems: list[str] = Field(default_factory=list)
    inbound_stems: list[str] = Field(default_factory=list)
