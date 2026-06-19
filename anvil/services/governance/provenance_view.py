"""Surfaced provenance record for a dataset or corpus.

Returned via API responses so users can inspect the source,
license, and attribution of any dataset or corpus.
"""

from pydantic import BaseModel

from .data_origin import DataOrigin


class ProvenanceView(BaseModel):
    """Human-readable provenance metadata for a dataset or corpus.

    Parameters
    ----------
    source_description : str | None
        Where the data came from (e.g. "Project Gutenberg #11").
    license : str | None
        The license identifier (approved catalog entry or
        ``own-content`` sentinel).
    attribution : str | None
        Required attribution text. Empty string when the license
        requires none.
    origin : DataOrigin
        ``bundled`` (ships with the app) or ``user`` (supplied).
    """

    source_description: str | None = None
    license: str | None = None
    attribution: str | None = None
    origin: DataOrigin = DataOrigin.USER