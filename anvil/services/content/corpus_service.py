"""Corpus management service for the versioned content repository.

``CorpusService`` provides CRUD operations for versioned content
corpora, along with version listing, revert, and tagging.  It
orchestrates the :class:`ContentCorpusRepository` and
:class:`ContentVersionRepository` layers to enforce domain rules
(e.g., guarded deletion when run refs exist).
"""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from ...db.models.content_corpus import ContentCorpus
from ...db.models.content_tag import ContentTag
from ...db.repositories.content_corpora import ContentCorpusRepository
from ...db.repositories.content_sources import ContentSourceRepository
from ...db.repositories.content_versions import ContentVersionRepository
from .version_ref import VersionRef
from .versioned_content_store import VersionedContentStore


class CorpusService:
    """Domain service for content corpus lifecycle management.

    Parameters
    ----------
    corpus_repo : ContentCorpusRepository
        Repository for ``ContentCorpus`` entities.
    source_repo : ContentSourceRepository
        Repository for ``ContentSource`` entities.
    version_repo : ContentVersionRepository
        Repository for ``ContentVersion`` and ``ContentEntry``
        entities.
    db_session : AsyncSession
        SQLAlchemy async session for direct model persistence (e.g.
        tags).
    content_store : VersionedContentStore or None
        Content store for revert operations.  When ``None``, revert
        raises ``ValueError``.
    """

    def __init__(
        self,
        corpus_repo: ContentCorpusRepository,
        source_repo: ContentSourceRepository,
        version_repo: ContentVersionRepository,
        db_session: AsyncSession,
        content_store: VersionedContentStore | None = None,
    ) -> None:
        self._corpus_repo = corpus_repo
        self._source_repo = source_repo
        self._version_repo = version_repo
        self._db_session = db_session
        self._content_store = content_store

    # ── CRUD ────────────────────────────────────────────────────────

    async def create(
        self,
        name: str,
        slug: str,
        description: str | None = None,
        chunking_strategy: str = "windowed",
        block_size: int = 16,
        chunk_overlap: float = 0.5,
        source_description: str | None = None,
        attribution_text: str | None = None,
        origin: str = "user",
    ) -> ContentCorpus:
        """Create a new content corpus.

        Parameters
        ----------
        name : str
            Human-readable corpus name.
        slug : str
            Unique machine-readable identifier.
        description : str, optional
            Optional description.
        chunking_strategy : str
            Chunking algorithm name.  Defaults to ``"windowed"``.
        block_size : int
            Token block size.  Defaults to ``16``.
        chunk_overlap : float
            Fractional overlap between chunks.  Defaults to ``0.5``.
        source_description : str, optional
            Provenance source description.
        attribution_text : str, optional
            Attribution text for license compliance.
        origin : str
            Origin discriminator.  Defaults to ``"user"``.

        Returns
        -------
        ContentCorpus
            The newly created corpus ORM instance.
        """
        corpus = ContentCorpus(
            slug=slug,
            name=name,
            description=description,
            chunking_strategy=chunking_strategy,
            block_size=block_size,
            chunk_overlap=chunk_overlap,
            source_description=source_description,
            attribution_text=attribution_text,
            origin=origin,
        )
        return await self._corpus_repo.add(corpus)

    async def get(self, id: int) -> ContentCorpus | None:
        """Retrieve a content corpus by its primary key.

        Parameters
        ----------
        id : int
            Primary key of the corpus to retrieve.

        Returns
        -------
        ContentCorpus or None
            The matching corpus, or ``None`` if not found.
        """
        return await self._corpus_repo.get(id)

    async def get_by_slug(self, slug: str) -> ContentCorpus | None:
        """Retrieve a content corpus by its unique slug.

        Parameters
        ----------
        slug : str
            Unique slug to look up.

        Returns
        -------
        ContentCorpus or None
            The matching corpus, or ``None`` if not found.
        """
        return await self._corpus_repo.get_by_slug(slug)

    async def list(self) -> Sequence[ContentCorpus]:
        """List all content corpora, newest first.

        Returns
        -------
        Sequence of ContentCorpus
            All corpora ordered by creation date descending.
        """
        return await self._corpus_repo.get_all()

    async def delete(self, id: int) -> bool:
        """Delete a content corpus by its primary key.

        Refuses deletion if any version of the corpus has associated
        MLflow run references (run_refs).  This prevents accidental
        removal of content that has been used in experiments.

        Parameters
        ----------
        id : int
            Primary key of the corpus to delete.

        Returns
        -------
        bool
            ``True`` if the corpus was deleted, ``False`` if no
            matching corpus was found.

        Raises
        ------
        ValueError
            If any version of the corpus has run references.
        """
        corpus = await self._corpus_repo.get(id)
        if corpus is None:
            return False

        versions = await self._version_repo.list_by_corpus(id)
        for version in versions:
            run_refs = await self._version_repo.get_run_refs(version.id)
            if run_refs:
                raise ValueError(
                    f"Corpus {id} has versions with run references; "
                    f"refusing deletion"
                )

        return await self._corpus_repo.delete(id)

    # ── Versions ────────────────────────────────────────────────────

    async def list_versions(self, corpus_id: int) -> Sequence[ContentCorpus]:
        """List all versions of a corpus, newest first.

        Parameters
        ----------
        corpus_id : int
            Primary key of the corpus whose versions to list.

        Returns
        -------
        Sequence of ContentCorpus
            All ``ContentVersion`` records for the corpus (return type
            is ``ContentCorpus`` for API compatibility; see
            :meth:`ContentVersionRepository.list_by_corpus`).
        """
        return await self._version_repo.list_by_corpus(corpus_id)  # type: ignore[return-value]

    async def revert(self, corpus_id: int, to_version_id: int) -> VersionRef:
        """Revert a corpus to a previous version.

        Delegates to the content store's :meth:`revert` method.

        Parameters
        ----------
        corpus_id : int
            Primary key of the corpus to revert.
        to_version_id : int
            Primary key of the version to revert to.

        Returns
        -------
        VersionRef
            Reference to the newly created revert version.

        Raises
        ------
        ValueError
            If no content store is configured or the corpus/version
            is not found.
        """
        if self._content_store is None:
            raise ValueError("Content store not configured; revert unavailable")

        corpus = await self._corpus_repo.get(corpus_id)
        if corpus is None:
            raise ValueError(f"Corpus not found: {corpus_id}")

        version = await self._version_repo.get(to_version_id)
        if version is None:
            raise ValueError(f"Version not found: {to_version_id}")

        version_ref = VersionRef(
            manifest_digest=version.manifest_digest,
            version_id=version.id,
            version_number=version.version_number,
        )
        await self._content_store.revert(corpus.slug, version_ref)

        # Return the new HEAD version ref.
        updated_corpus = await self._corpus_repo.get(corpus_id)
        if updated_corpus is None or updated_corpus.current_version_id is None:
            raise ValueError("Revert failed: no current version set")

        new_version = await self._version_repo.get(updated_corpus.current_version_id)
        if new_version is None:
            raise ValueError("Revert failed: new version not found")

        return VersionRef(
            manifest_digest=new_version.manifest_digest,
            version_id=new_version.id,
            version_number=new_version.version_number,
        )

    # ── Tagging ─────────────────────────────────────────────────────

    async def tag(self, version_id: int, name: str) -> ContentTag:
        """Tag a version with a human-readable name.

        Creates a :class:`ContentTag` with ``gc_protected=True`` so
        the tagged version is preserved during garbage collection.

        Parameters
        ----------
        version_id : int
            Primary key of the version to tag.
        name : str
            Unique tag name.

        Returns
        -------
        ContentTag
            The newly created tag.

        Raises
        ------
        ValueError
            If a tag with the given name already exists.
        """
        # Verify the version exists.
        version = await self._version_repo.get(version_id)
        if version is None:
            raise ValueError(f"Version not found: {version_id}")

        tag = ContentTag(
            version_id=version_id,
            name=name,
            gc_protected=True,
        )
        self._db_session.add(tag)
        await self._db_session.flush()
        await self._db_session.refresh(tag)
        return tag

    # ── Version diff ────────────────────────────────────────────────

    async def version_diff(self, version_id: int) -> dict:
        """Compute added/removed paths between a version and its
        immediate predecessor.

        Compares a version's entries against those of the prior version
        (``version_number - 1`` in the same corpus) to produce a diff
        of added and removed paths.  If this is the first version (no
        prior), all entries are reported as added.

        Parameters
        ----------
        version_id : int
            Primary key of the version to diff.

        Returns
        -------
        dict
            A dict with keys:
            - ``"added"``: list of paths present in this version but
              absent from its predecessor.
            - ``"removed"``: list of paths absent in this version but
              present in its predecessor.
            - ``"version_number"``: version number of the diffed version.
            - ``"prior_version_number"``: version number of the prior
              version, or ``None`` for the first version.
        """
        version = await self._version_repo.get(version_id)
        if version is None:
            raise ValueError(f"Version not found: {version_id}")

        current_entries = await self._version_repo.get_entries(version_id)
        current_paths = {e.path for e in current_entries}

        # Find the prior version (same corpus, version_number - 1).
        prior_version_number = None
        prior_paths: set[str] = set()
        if version.version_number > 1:
            corpus_versions = await self._version_repo.list_by_corpus(version.corpus_id)
            for v in corpus_versions:
                if v.version_number == version.version_number - 1:
                    prior_entries = await self._version_repo.get_entries(v.id)
                    prior_paths = {e.path for e in prior_entries}
                    prior_version_number = v.version_number
                    break

        added = sorted(current_paths - prior_paths)
        removed = sorted(prior_paths - current_paths)

        return {
            "added": added,
            "removed": removed,
            "version_number": version.version_number,
            "prior_version_number": prior_version_number,
        }
