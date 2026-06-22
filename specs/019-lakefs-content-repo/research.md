# Phase 0 Research: Content Repository (versioned, reproducible training data)

**Feature**: `016-lakefs-content-repo` | **Date**: 2026-06-20 | **Spec**: [spec.md](./spec.md)

This document resolves the Technical Context unknowns and records the binding
architecture decisions. The single most consequential decision (D1) is the
**substrate** for local mode; every other decision follows from it.

---

## D1 — Substrate for LOCAL mode: pure-Python content-addressed store, NOT LakeFS

**Decision**: Local mode does **not** run LakeFS. The versioned content repository
in local mode is implemented in **pure Python** as a content-addressed blob store
(over the existing `LocalFileStore`) plus SQLite metadata. A `VersionedContentStore`
interface (D2) abstracts the substrate so that **SaaS mode MAY later use a
LakeFS-backed implementation** behind the same interface. LakeFS is therefore a
**SaaS-mode, future-delivery** concern — not part of the first (local) delivery.

**Rationale** (driven by research findings + spec constraints):

1. **Zero-config / pip-installable / transparent (US8, FR-039/040, Constitution
   Article IX "Pit of Success").** LakeFS server is a **Go binary (~50–100 MB), not
   pip-installable**; there is no pure-Python server. Shipping it as a transparent
   local sidecar would require downloading/bundling a per-platform binary — a sharp
   departure from the MLflow sidecar (which is merely a pip dependency). A pure-Python
   store ships in the wheel with zero extra binaries and zero user setup, satisfying
   US8 directly and Article IX ("works with no config, never crash").
2. **The headline RBAC feature is enterprise-only.** OSS LakeFS provides only a single
   admin credential + flat access keys — **no per-branch write scoping, no merge
   restriction policies**. The draft's "scope injector keys to `ingest/<source>/**`,
   forbid merge" (FR-007/FR-036) is **impossible in OSS LakeFS**. Producer scoping must
   be enforced at the app layer regardless — so LakeFS buys us nothing here.
3. **Pre-\* hook loopback deadlock.** LakeFS locks the branch during `pre-commit`/
   `pre-merge` hooks and calls back via webhook into the **same** FastAPI process; the
   hook cannot write to the locked branch and must finish fast. In-process validation
   (no LakeFS) eliminates this hazard entirely and makes gates plain testable Python.
4. **The spec is deliberately substrate-agnostic.** Reproducibility-by-reference,
   immutable versions, concurrent isolated ingestion, and validation gates are all
   achievable without LakeFS (see D3–D5).

**Alternatives considered**:

- *LakeFS as a managed local sidecar (download/bundle binary)* — rejected: violates
  pip/zero-config promise, ~512 MB RAM idle cost, GC unsupported with local blockstore,
  and still needs app-level RBAC. Highest risk, lowest payoff for local mode.
- *Require LakeFS in PATH / Docker spawn* — rejected: breaks "works out of the box" and
  adds a Docker/daemon dependency to a single-machine educational tool.
- *git or DVC as the local versioning engine* — rejected: git is poor at large binary
  blobs and adds a subprocess dependency; DVC adds a heavy dependency tree and its own
  CLI/cache model. A small content-addressed store is simpler, dependency-free, and
  fully under our control/testing.

**Consequence for the spec**: No spec requirement changes — the spec never mandated
LakeFS in the body (only the feature title/draft did). LakeFS is reclassified as the
**SaaS-mode substrate** (future). The feature directory name (`016-lakefs-content-repo`)
is retained for traceability; an ADR will record this divergence from the draft.

---

## D2 — Interface boundary: a `VersionedContentStore` abstraction (distinct from `FileStore`)

**Decision**: Introduce a new async abstraction **`VersionedContentStore`** that models
versioned, ingestion-oriented operations — NOT the blob-level `FileStore`. The local
implementation (`LocalVersionedContentStore`) composes the existing `FileStore`
(`LocalFileStore`) for byte storage and SQLite for metadata. A future
`LakeFSVersionedContentStore` (SaaS) implements the same interface.

**Operations** (all async):
- `create_corpus(...) -> CorpusRef`
- `open_session(corpus, source) -> SessionRef` (opens an isolated staging workspace)
- `stage(session, path, bytes) -> staged entry` (writes into session-scoped staging)
- `validate_session(session) -> ValidationReport` (runs gates; read-only vs canonical)
- `accept_session(session) -> AcceptResult` (serialized atomic fold into canonical)
- `abandon_session(session)`
- `freeze_version(corpus, selection|None) -> VersionRef` (immutable snapshot/composition)
- `resolve(version_ref) -> Manifest(entries=[(path, weight, content_hash)], chunk_cfg)`
- `open_blob(content_hash) -> async byte stream` (content-addressed read)
- `tag(version_ref, name)` / `revert(corpus, to_version_ref)`

**Rationale**: The existing `FileStore` ABC (`get/put` streams) is blob-level and
intentionally unchanged. Versioning/ingestion/composition are a **different bounded
context** (Constitution Article X) and belong in a content-repository domain service,
not bolted onto `FileStore`. This keeps `FileStore` stable and lets LakeFS slot in later
without touching the service/route layers.

**Placement** (layered architecture, Article VII + X):
- Domain sub-package `anvil/services/content/` (new bounded context).
- Interface + local impl live there for local mode. The future LakeFS impl lives in
  `anvil/_saas/` (per ADR-030; not built now).
- SQLite metadata via new repositories in `anvil/db/repositories/`.
- Exposed through `AnvilWorkbench` (God Class) accessors; routes call the workbench.

**Alternatives considered**: Extending `FileStore` with versioning ops — rejected
(conflates bounded contexts, bloats a stable interface, and the SaaS `FileStore`
contract is already bytes-vs-stream incompatible). Reconciling the two `FileStore`
variants is **out of scope** for this feature.

---

## D3 — Reproducibility-by-reference: content-addressed manifest digest

**Decision**: A **Content Version** is identified by a **manifest digest**: blobs are
stored content-addressed by `sha256` of their bytes (naturally immutable + dedup'd); a
version's manifest is the canonical-JSON of its sorted entries
`[(path, content_hash, weight, source_id)]` + chunk config; the manifest's `sha256` is
the **pinnable, opaque version ref** logged to MLflow (replacing the draft's LakeFS
commit hash).

**Rationale**:
- **Immutability (FR-004)**: content-addressing makes a version's bytes and manifest
  cryptographically immutable — changing any entry changes the digest, yielding a new
  version, never mutating the old.
- **Identical re-resolution (FR-003, SC-001)**: a digest deterministically resolves to
  the exact entry set → exact content-addressed blobs, regardless of later corpus
  changes.
- **Retention protection (FR-024, SC-002)**: GC walks reachable manifests; any manifest
  digest referenced by a training run (and its blobs) is reachable and never collected —
  the content-addressed analogue of LakeFS's `gc_protected` tag.
- **MLflow wiring**: log the manifest digest as `corpus_ref` param + a
  `MetaDataset(source="anvil-content://<corpus>/<digest>", digest=<digest>)` input, and
  attach `corpus_manifest.json` as the portable, self-describing fallback (matches the
  draft's §6 two-step, minus per-file artifact duplication).

**Alternatives**: monotonic integer version ids only (no integrity guarantee — rejected
as the sole ref; we keep a human-friendly `v<n>` label *in addition* to the digest).

---

## D4 — Concurrent isolated ingestion + serialized acceptance (app-level, no LakeFS hooks)

**Decision**: Ingestion sessions are isolated by writing staged blobs into a
**session-scoped staging area** (content-addressed, namespaced by session id) with
metadata rows scoped to the session; the canonical corpus state is untouched until
acceptance. **Acceptance is serialized per corpus** via an in-process async lock +
a single SQLite write transaction (SQLite is single-writer), making the fold atomic.
Producers are **scoped at the app layer** (a session may only write to its own staging;
only the acceptance flow mutates canonical state) — replacing the impossible OSS LakeFS
RBAC.

**Rationale**: In-process isolation/serialization is **superior to LakeFS hooks here**:
fully testable Python, no branch-lock deadlock, no enterprise-RBAC dependency, and a
natural fit for SQLite's single-writer model + the async stack (Article V). Content-
addressed blobs mean concurrent sessions writing identical bytes simply converge on the
same hash with no conflict.

**Validation gates as in-process service calls**:
- **Per-batch (fast, ~5s, FR-012)**: UTF-8/readability, size bounds, required provenance
  metadata, intra-batch exact dedup — runs on staged session content, read-only vs
  canonical.
- **Pre-acceptance (~30s, FR-013)**: cross-corpus exact dedup (by content hash — O(1)
  set lookups), language allowlist, sensitive-info scan, shape conformance — runs before
  the serialized fold.
- **Fail-closed (FR-016)**: any gate error/timeout → reject, canonical unchanged.
- **Post-acceptance advisory (FR-015, FR-026a)**: near-dup detection + re-tokenize +
  stats/lineage run after the fold, non-blocking (an async task, never reverts).

**Alternatives**: multi-process/file-locking — unnecessary for a single-machine local
app; revisit only if a multi-writer SaaS backend (LakeFS) demands it (handled by that
impl).

---

## D5 — Validation, dedup, and near-dup specifics

- **Exact dedup** = equality of content `sha256` (intra-batch set + cross-corpus set
  lookup). Effectively free given content-addressing.
- **Near-dup** = advisory post-acceptance job; algorithm deferred to implementation
  (e.g., shingled MinHash/Jaccard over normalized text); flags only (FR-015).
- **Sensitive-info / license gates** reuse the existing **governance** services
  (`GovernanceService`, license catalog, `AuditService`) rather than a parallel
  mechanism (spec Assumptions; Article VII).
- **Accepted content type** = any readable UTF-8 text, extension-agnostic; binary
  rejected by the readability gate (spec Clarification Q3).

---

## D6 — Operating-mode mechanics

- **Local mode (this delivery)**: pure-Python `LocalVersionedContentStore`; **no new
  managed sidecar** (the MLflow-sidecar supervisor pattern is documented for reference
  but NOT needed, since there is no external content service to supervise locally). This
  is a major simplification versus the draft.
- **SaaS mode (future)**: `LakeFSVersionedContentStore` behind the same interface, run as
  a managed component with full visibility (FR-041). The MLflow `MLflowService`
  supervisor pattern (`anvil/supervisor/services.py`) is the template **if/when** a
  managed LakeFS process is introduced for SaaS-dev; production SaaS uses hosted LakeFS.
- **Mode/backend selection seam**: `AnvilWorkbench` currently hardcodes `LocalFileStore`.
  Introduce a content-store accessor on the workbench that returns the local impl now;
  the SaaS factory (`anvil/_saas/`, per ADR-030) will inject the LakeFS impl later. The
  unimplemented `ANVIL_MODE`/`ANVIL_STORAGE_BACKEND` wiring is **not** completed by this
  feature beyond what the content store needs.

---

## D7 — Management UI

- Forge screens are standard Jinja pages extending `base.html`, wired into
  `anvil/api/v1/pages.py` + a nav tab, using the existing SSE pattern
  (`StreamingResponse` + `asyncio.Queue`, client `SSESession` in `sse.js`) for the live
  Injection Monitor / Import Console. No "CRT/glitch TUI" — the actual design system is
  iOS-modern (draft assumption corrected during analysis). No "dual-UI feature flags"
  exist; theme system is `data-skin`/`data-theme`.
- **SQLAdmin** (`sqladmin>=0.27`, async-capable) MAY be mounted at `/admin` for
  back-office (FR-037) — `add_view`s must be registered at app construction (not in
  lifespan). This is **optional / lower-priority**; the management plane is the forge
  screens. New dependency requires an ADR (Constitution).

---

## D8 — New dependencies

- **Local mode (this delivery)**: **zero new runtime dependencies** — pure stdlib
  (`hashlib`, `json`) over existing `LocalFileStore` + async SQLAlchemy. (Aligns with
  the lean-deps constraint; no ADR-worthy dep additions for local mode.)
- **SaaS mode (future, separate ADR)**: `lakefs` / `lakefs-spec`, and optionally
  `sqladmin` for `/admin`. Confined to optional extras + `anvil/_saas/`.

---

## Resolved Technical Context

| Field | Value |
|---|---|
| Language/Version | Python 3.11+ |
| Primary Dependencies | FastAPI, async SQLAlchemy + aiosqlite, Alembic, Jinja2, MLflow (existing). **No new local runtime deps.** |
| Storage | SQLite (`data/anvil-state.db`) for metadata; content-addressed blobs on filesystem via `LocalFileStore` (`data/content/`). SaaS (future): LakeFS + object store. |
| Testing | pytest + pytest-asyncio + httpx; TDD, ratcheting coverage (Article IV) |
| Target Platform | macOS/Linux, local-first single process; SaaS later |
| Project Type | Web service (FastAPI) + Jinja UI, layered |
| Performance Goals | Per-batch validation ~5 s; pre-acceptance ~30 s (SC-012) |
| Constraints | Zero-config local (US8); async throughout (Art. V); isolation/serialization correctness at host-supported concurrency (SC-003) |
| Scale/Scope | Single-machine local; text content v1; concurrency correctness over throughput |

All NEEDS CLARIFICATION resolved.
