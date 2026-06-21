"""Composition service — weighted composition of corpus entries.

``CompositionService`` enables users to compose a virtual version by
selecting entries from one or more source corpora with explicit
sampling weights.  It provides preview (estimating token/byte
contribution per entry) and freeze (creating an immutable composition
version) operations.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...db.repositories.content_corpora import ContentCorpusRepository
from ...db.repositories.content_versions import ContentVersionRepository
from .manifest import ManifestEntry
from .version_ref import VersionRef
from .versioned_content_store import VersionedContentStore


class CompositionService:
    """Service for creating weighted compositions of corpus entries.

    Allows users to select content blobs from one or more source
    corpora, assign sampling weights, preview the resulting data
    contribution (bytes / tokens), and freeze an immutable composition
    version.

    Parameters
    ----------
    store : VersionedContentStore
        The content store for blob metadata access and version
        freezing.
    version_repo : ContentVersionRepository
        Repository for version metadata.
    corpus_repo : ContentCorpusRepository
        Repository for corpus lookups.
    db_session : AsyncSession
        SQLAlchemy async session for direct blob-size queries.
    """

    def __init__(
        self,
        store: VersionedContentStore,
        version_repo: ContentVersionRepository,
        corpus_repo: ContentCorpusRepository,
        db_session: AsyncSession,
    ) -> None:
        self._store = store
        self._version_repo = version_repo
        self._corpus_repo = corpus_repo
        self._db_session = db_session

    def validate_spec(self, spec: list[dict]) -> None:
        """Validate a composition specification.

        Checks that *spec* is non-empty and the sum of all weights
        is strictly positive.  Raises ``ValueError`` on violation.

        Parameters
        ----------
        spec : list of dict
            Composition specification.  Each dict must have keys
            ``content_hash`` (str) and ``weight`` (float).

        Raises
        ------
        ValueError
            If *spec* is empty or the total weight sum is not
            positive.
        """
        if not spec:
            raise ValueError("Composition spec must not be empty")

        total_weight = sum(item.get("weight", 0.0) for item in spec)
        if total_weight <= 0:
            raise ValueError("Composition spec weights must sum to a positive value")

    async def preview(self, corpus_id: int, spec: list[dict]) -> dict:
        """Preview the token/byte contribution of a composition spec.

        Accepts a list of ``{"content_hash": str, "weight": float}``
        dicts, validates the spec, looks up each blob's size from the
        content store, and returns a summary of per-entry contributions
        plus totals.

        Token count is a rough estimate: ``tokens ~ bytes / 4``.

        Parameters
        ----------
        corpus_id : int
            Primary key of the target corpus (used for validation).
        spec : list of dict
            Composition specification. Each dict must have keys
            ``content_hash`` (str) and ``weight`` (float).

        Returns
        -------
        dict
            A dict with:
            - ``sources``: list of ``{"path": str, "bytes": int,
              "weight": float}`` per entry.
            - ``total_bytes``: int, total size across all entries.
            - ``total_tokens``: int, estimated token count.

        Raises
        ------
        ValueError
            If the spec is empty, all weights sum to zero, or the
            corpus is not found.
        """
        self.validate_spec(spec)

        corpus = await self._corpus_repo.get(corpus_id)
        if corpus is None:
            raise ValueError(f"Corpus not found: id={corpus_id}")

        from ...db.models.content_blob import ContentBlob

        sources: list[dict] = []
        total_bytes = 0

        for item in spec:
            content_hash = item["content_hash"]
            weight = item["weight"]

            result = await self._db_session.execute(
                select(ContentBlob).where(ContentBlob.content_hash == content_hash)
            )
            blob = result.scalar_one_or_none()
            size_bytes = blob.size_bytes if blob is not None else 0

            sources.append(
                {
                    "path": content_hash,
                    "bytes": size_bytes,
                    "weight": weight,
                }
            )
            total_bytes += size_bytes

        return {
            "sources": sources,
            "total_bytes": total_bytes,
            "total_tokens": total_bytes // 4,
        }

    async def freeze(self, corpus_id: int, spec: list[dict]) -> VersionRef:
        """Freeze a composition version from a specification.

        Converts each spec item to a ``ManifestEntry`` and delegates
        to ``store.freeze_version()`` with ``composition=entries``.
        Validates that the spec is non-empty and the sum of all
        weights is greater than zero.

        Parameters
        ----------
        corpus_id : int
            Primary key of the target corpus.
        spec : list of dict
            Composition specification. Each dict must have keys
            ``content_hash`` (str) and ``weight`` (float).

        Returns
        -------
        VersionRef
            Reference to the newly frozen composition version.

        Raises
        ------
        ValueError
            If the corpus is not found, the spec is empty, or the
            sum of weights is zero.
        """
        self.validate_spec(spec)

        corpus = await self._corpus_repo.get(corpus_id)
        if corpus is None:
            raise ValueError(f"Corpus not found: id={corpus_id}")

        entries = [
            ManifestEntry(
                path=item["content_hash"],
                content_hash=item["content_hash"],
                weight=item.get("weight", 1.0),
            )
            for item in spec
        ]

        return await self._store.freeze_version(
            corpus.slug,
            composition=entries,
        )
