---
title: "ADR-033: Content Repository Substrate — Pure-Python Local, LakeFS for SaaS"
type: decision
tags:
  - type/decision
  - domain/content
  - domain/architecture
  - domain/infrastructure
  - domain/database
created: 2026-06-20
updated: 2026-06-20
aliases:
  - "ADR-033: Content Repository Substrate — Pure-Python Local, LakeFS for SaaS"
  - ADR-033
status: status/draft
source: agent
code-refs:
  - specs/016-lakefs-content-repo/spec.md
  - specs/016-lakefs-content-repo/plan.md
  - specs/016-lakefs-content-repo/research.md
  - specs/016-lakefs-content-repo/contracts/versioned-content-store.md
  - specs/014-saas-architecture/spec.md
---

# ADR-033: Content Repository Substrate — Pure-Python Local, LakeFS for SaaS

## Status

Proposed

## Context

Feature 016 (Content Repository) introduces a versioned, reproducible content
substrate: a canonical **Corpus**, immutable **Content Versions** pinned by training
runs for reproducibility, concurrent **isolated ingestion** from multiple producers,
automated **validation gates**, weighted **composition/ensembling**, lineage, and a
management UI. The source design draft (`docs/anvil-content-repo-lakefs-draft.md`)
assumed **LakeFS over MinIO over Postgres** as the substrate, with LakeFS hooks for
validation and LakeFS RBAC for producer scoping.

Two hard product constraints and three research findings forced a re-evaluation:

**Constraints**
- **Local-first, zero-config, pip-installable.** Local users must run everything
  self-contained and transparently — the way the MLflow sidecar works today — with no
  setup and no awareness of supporting services (016 US8/FR-039/040; Constitution
  Article IX, "Pit of Success").
- **SaaS as a fully managed, visible component** (016 US9/FR-041) — but it need not ship
  in the same delivery, only not be precluded.

**Research findings** (016 `research.md`, validated against LakeFS docs):
1. **LakeFS is a Go binary (~50–100 MB), not pip-installable**; no pure-Python server
   exists. Running it as a transparent local sidecar would require downloading/bundling
   a per-platform binary — a sharp departure from "MLflow is just a pip dependency."
2. **LakeFS fine-grained RBAC is enterprise-only.** OSS LakeFS provides only a single
   admin credential + flat access keys — no per-branch write scoping, no merge
   restriction. The draft's "scope injector keys to `ingest/<source>/**`, forbid merge"
   is impossible in OSS; producer scoping must be enforced at the app layer regardless.
3. **Pre-\* hook loopback deadlock.** LakeFS locks the branch during `pre-commit`/
   `pre-merge` hooks and calls back via webhook into the same FastAPI process; the hook
   cannot write to the locked branch and must finish fast. In-process validation avoids
   this entirely.

The 016 spec is deliberately **substrate-agnostic** — reproducibility-by-reference,
immutable versions, isolated ingestion, and validation gates do not require LakeFS.

## Decision

Front the content repository with a **`VersionedContentStore`** interface (distinct from
the blob-level `FileStore`). Select the implementation by operating mode:

- **Local mode** uses a **pure-Python, content-addressed** implementation
  (`LocalVersionedContentStore`) over the existing `LocalFileStore` + SQLite metadata.
  **No LakeFS, no object store, no new runtime dependency, no managed sidecar.**
- **SaaS mode** (future, owned by the 014 body of work) uses a **LakeFS-backed**
  implementation (`LakeFSVersionedContentStore`) over the org-scoped S3 bucket, behind
  the same interface, presented as a managed component.

Cross-cutting decisions that hold in **both** modes:

- **Reproducibility = content-addressed manifest digest.** Blobs are stored by `sha256`
  (immutable, dedup'd). A version's manifest (sorted `(path, content_hash, weight,
  source)` + chunk config) is canonical-JSON-hashed to a **manifest digest** — the
  opaque, pinnable ref logged to MLflow (`corpus_ref`). This is the external ref in both
  modes; LakeFS commit refs (if used by the SaaS impl) are internal only.
- **Validation, isolation, and serialized acceptance are app-level / in-process** — NOT
  LakeFS hooks. Per-batch gates (~5 s) and cross-corpus pre-acceptance gates (~30 s) run
  in the service layer; acceptance is serialized per corpus (asyncio lock + single SQLite
  write txn locally); gates fail closed.
- **Producer + management authorization is app-level.** Data-plane scoping (a session may
  only write its own staging) and management-action authz (rename/tag/compose/promote/
  lock) are enforced in the application, with a documented seam where SaaS injects
  multi-principal RBAC (org/team/role). OSS LakeFS RBAC is never relied upon for tenant
  isolation.

## Consequences

### Positive

- **Local mode stays zero-config and dependency-free** — ships in the wheel, no binary
  download, satisfies Article IX and 016 US8 directly.
- **No enterprise-RBAC dependency** — tenant isolation is owned by the app in both modes.
- **No hook loopback hazard** — validation is plain, testable Python.
- **Stronger reproducibility** — content-addressing makes immutability and identical
  re-resolution cryptographic, not convention.
- **Clean SaaS swap** — LakeFS slots in behind one interface without touching the
  service/route/UI layers; parity is guaranteed by the shared interface + digest model.

### Negative

- **We build a small content-addressed store + manifest layer** instead of delegating to
  LakeFS locally. Mitigated: the surface is small (put/open by hash, manifest digest,
  isolated staging, serialized fold) and fully under our test/control.
- **Two implementations to keep in parity.** Mitigated: a single ABC + a shared
  contract-test suite (VCS-1..VCS-7) run against both.
- **App-level concurrency control** (serialized acceptance) rather than a distributed
  substrate. Fine for single-machine local; the SaaS impl handles multi-writer concerns.

### Risks

- **Near-duplicate detection** algorithm is deferred (advisory, post-acceptance) — record
  the chosen approach (e.g., shingled MinHash/Jaccard threshold) when implemented.
- **SaaS LakeFS operational maturity** (GC, sizing, hooks-free integration) is validated
  in the 014 delivery, not here.

## Alternatives Considered

- **LakeFS as a managed local sidecar (download/bundle the binary).** Rejected: violates
  the pip/zero-config promise, ~512 MB idle RAM, GC unsupported with the local blockstore,
  and still needs app-level RBAC.
- **Require LakeFS in PATH / Docker spawn locally.** Rejected: breaks "works out of the
  box"; adds a Docker/daemon dependency to a single-machine educational tool.
- **git or DVC as the local versioning engine.** Rejected: git handles large binary blobs
  poorly and adds a subprocess dependency; DVC adds a heavy dependency tree and its own
  cache/CLI model. A small content-addressed store is simpler and dependency-free.
- **Extend the existing `FileStore` with versioning ops.** Rejected: conflates bounded
  contexts and bloats a stable interface; the SaaS `FileStore` contract is already
  bytes-vs-stream incompatible. Versioning lives in a separate `VersionedContentStore`.

## SaaS Integration Hand-off

The SaaS-mode consequences are owned by the 014 body of work and are recorded there:

- `specs/014-saas-architecture/spec.md`: `VersionedContentStore` added to the abstraction
  interfaces (FR-016); **Content Repository (versioned)** requirement group
  **FR-062–FR-067**; **SC-021** (cross-mode parity + org isolation); **AD-17**.
- [[ADR-030-saas-architecture|ADR-030]]: abstraction table grown to six interfaces;
  canonical decisions extended with **AD-17**.
- [[SaaSArchitecture]]: `anvil-content-{env}` LakeFS bucket/namespace + content-repo notes.

The SaaS implementation MUST: keep validation/isolation/acceptance in-process (not LakeFS
hooks); enforce org/team/role isolation at the app layer (not OSS LakeFS RBAC); preserve
the manifest digest as the external reproducibility ref; and confine `lakefs`/`lakefs-spec`
(and optional `sqladmin` for `/admin`) to optional extras under `anvil/_saas/` so local
mode gains no new dependency.

## Relationship to Other Decisions

- Complements [[ADR-032-greenfield-legacy-removal|ADR-032 (Greenfield Legacy Removal)]]:
  016 is a clean implementation — the canonical unit is "Corpus"; legacy directory-based
  corpus support, migration, and backward compatibility are out of scope (016 FR-038/038a–c).
- Builds on [[ADR-019-pydantic-basemodel-over-dataclass|ADR-019]] (Pydantic value types),
  [[ADR-020-one-class-per-file|ADR-020]] (one class per file),
  [[ADR-022-domain-driven-package-decomposition|ADR-022]] (domain-driven decomposition —
  new `anvil/services/content/`).

## See Also

[[ADR-030-saas-architecture|ADR-030: SaaS Architecture]], [[SaaSArchitecture]],
[[ADR-032-greenfield-legacy-removal|ADR-032: Greenfield Legacy Removal]].
