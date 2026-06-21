"""Manifest value types and canonical-digest helper.

A ``Manifest`` is a versioned snapshot of a corpus's entries at a point
in time. The canonical digest (SHA-256 of canonical JSON) serves as an
immutable content fingerprint for version pinning and integrity verification.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from pydantic import BaseModel, Field


class ManifestEntry(BaseModel):
    """A single entry within a versioned manifest.

    Parameters
    ----------
    path : str
        Relative path of the content within the corpus.
    content_hash : str
        SHA-256 hex digest of the blob content.
    weight : float
        Sampling weight for composition. Defaults to ``1.0``.
    source : str | None
        Optional identifier for the entry's origin (e.g. source corpus
        slug or injector name). ``None`` when the entry originated in
        this corpus.
    """

    path: str
    content_hash: str
    weight: float = 1.0
    source: str | None = None


class Manifest(BaseModel):
    """Versioned snapshot of a corpus's content entries.

    Parameters
    ----------
    corpus_slug : str
        Unique slug identifying the corpus.
    version_number : int
        Monotonically increasing version number within the corpus.
    is_composition : bool
        ``True`` when this manifest was produced by composing entries
        from one or more source corpora (a virtual version).
    chunk_cfg : dict[str, Any]
        Chunking configuration dict with keys ``strategy``, ``block_size``,
        and ``chunk_overlap``.
    entries : list[ManifestEntry]
        Ordered list of content entries in this version.
    """

    corpus_slug: str
    version_number: int
    is_composition: bool = False
    chunk_cfg: dict[str, Any] = Field(default_factory=dict)
    entries: list[ManifestEntry] = Field(default_factory=list)


def compute_manifest_digest(manifest: Manifest) -> str:
    """Compute the canonical SHA-256 digest of a manifest.

    The digest is computed by:

    1. Sorting ``manifest.entries`` by ``(path, content_hash)``.
    2. Serialising the full manifest to canonical JSON (``sort_keys=True``,
       ``separators=(",", ":")``).
    3. Hashing the UTF-8 encoded JSON with SHA-256.

    Parameters
    ----------
    manifest : Manifest
        The manifest whose digest to compute.

    Returns
    -------
    str
        Lower-case hex SHA-256 digest.
    """
    sorted_entries = sorted(manifest.entries, key=lambda e: (e.path, e.content_hash))

    data = manifest.model_dump()
    data["entries"] = [e.model_dump() for e in sorted_entries]

    canonical = json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
