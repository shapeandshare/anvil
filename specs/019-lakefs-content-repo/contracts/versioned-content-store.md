# Contract: `VersionedContentStore` (substrate abstraction)

**Feature**: `016-lakefs-content-repo` | **Phase 1**

The substrate boundary (research D2). Local mode ships `LocalVersionedContentStore`
(pure-Python, content-addressed over `LocalFileStore` + SQLite). SaaS mode MAY later
add `LakeFSVersionedContentStore` behind the **same** interface (future). This interface
is distinct from the blob-level `FileStore` (which is left unchanged).

Location: `anvil/services/content/versioned_content_store.py` (ABC) and
`anvil/services/content/local_versioned_content_store.py` (local impl). All methods
async (Article V).

```python
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator

# Value types (Pydantic BaseModel, in anvil/services/content/):
#   IngestSessionRef, StagedEntry, ValidationReport, AcceptResult,
#   VersionRef, Manifest, ManifestEntry

class VersionedContentStore(ABC):
    """Versioned, ingestion-oriented content substrate.

    Immutability and reproducibility are guaranteed by content-addressing:
    a version is identified by a manifest digest over its sorted entries.
    """

    # ---- corpora ----
    @abstractmethod
    async def ensure_corpus(self, slug: str) -> None:
        """Idempotently ensure substrate-side storage exists for a corpus."""

    # ---- isolated ingestion ----
    @abstractmethod
    async def open_session(self, corpus_slug: str, source_slug: str) -> IngestSessionRef:
        """Open an isolated staging workspace. Staged content is invisible to
        other sessions and to the canonical corpus until acceptance (FR-006)."""

    @abstractmethod
    async def stage(
        self, session: IngestSessionRef, path: str, data: AsyncIterator[bytes]
    ) -> StagedEntry:
        """Write one entry into the session-scoped staging area, content-addressed.
        Returns the entry with its computed content_hash and size."""

    @abstractmethod
    async def validate_batch(self, session: IngestSessionRef) -> ValidationReport:
        """Run fast per-batch gates (read-only vs canonical), target ~5s (FR-012)."""

    @abstractmethod
    async def accept_session(self, session: IngestSessionRef) -> AcceptResult:
        """Run pre-acceptance gates (~30s, FR-013); on all-green, atomically and
        serially fold staged content into the canonical corpus and create a new
        ContentVersion. Fail-closed on any error/timeout (FR-014/016). Serialized
        per corpus (FR-010)."""

    @abstractmethod
    async def abandon_session(self, session: IngestSessionRef) -> None:
        """Discard a session's staging; canonical state untouched."""

    # ---- versions & composition ----
    @abstractmethod
    async def freeze_version(
        self, corpus_slug: str, composition: list[ManifestEntry] | None = None
    ) -> VersionRef:
        """Freeze an immutable version. If composition is None, snapshots current
        canonical content; otherwise freezes the weighted selection (US4). Returns
        the VersionRef carrying the manifest_digest (FR-001/004/020)."""

    @abstractmethod
    async def resolve(self, version_ref: VersionRef) -> Manifest:
        """Resolve a pinned version to its exact entries + chunk config. Stable
        regardless of later corpus changes (FR-003, SC-001)."""

    @abstractmethod
    async def open_blob(self, content_hash: str) -> AsyncIterator[bytes]:
        """Stream a content-addressed blob's bytes."""

    @abstractmethod
    async def revert(self, corpus_slug: str, to_version: VersionRef) -> None:
        """Repoint canonical 'latest' to a prior known-good version (FR-011)."""
```

**Contract guarantees** (must hold for every implementation):

| ID | Guarantee | Spec |
|---|---|---|
| VCS-1 | A `VersionRef.manifest_digest` resolves to a byte-identical entry set forever | FR-003, SC-001 |
| VCS-2 | Frozen versions are immutable; mutation creates a new version | FR-004 |
| VCS-3 | Staged content of a session is never visible to other sessions or canonical until accept | FR-006, SC-003 |
| VCS-4 | `accept_session` is atomic and serialized per corpus | FR-010 |
| VCS-5 | Validation failure or gate timeout leaves canonical unchanged (fail-closed) | FR-014, FR-016 |
| VCS-6 | Blobs referenced by any retention-protected version are never collected | FR-024, SC-002 |
| VCS-7 | Behavior is identical across local and (future) SaaS implementations | FR-042, SC-011 |

**Local implementation notes** (`LocalVersionedContentStore`):
- Blobs: `data/content/blobs/<first2>/<sha256>` via `LocalFileStore`.
- Staging: `data/content/staging/<staging_key>/...` (content-addressed too).
- `accept_session` uses an `asyncio.Lock` keyed by corpus + a single SQLite write txn.
- `manifest_digest` per `manifest.schema.md`.

**Future SaaS implementation notes** (`LakeFSVersionedContentStore`, not built now):
- Maps sessions→branches, accept→merge, version→commit/tag, resolve→`lakefs-spec` reads.
- Validation stays in-process (NOT LakeFS pre-* webhooks) to avoid branch-lock deadlock;
  LakeFS provides storage/versioning only.
