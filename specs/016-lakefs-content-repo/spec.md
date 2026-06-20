# Feature Specification: LakeFS Content Repository

**Feature Branch**: `016-lakefs-content-repo`
**Created**: 2026-06-20
**Status**: Draft
**Input**: User description: "LakeFS Content Repository" — with the operating-mode constraint that local users run everything self-contained and transparently (supporting services managed like the existing experiment-tracking sidecar, invisible to the user), while hosted (SaaS) users see it as a fully managed component with full visibility alongside other services.

## Clarifications

### Session 2026-06-20

- Q: What responsiveness target should the blocking validation gates meet? → A: Per-batch (fast) validation returns feedback within ~5 seconds for a typical batch; pre-acceptance (cross-corpus) validation within ~30 seconds.
- Q: What is the canonical name for the new versioned content unit, and what is the scope regarding the existing directory-based mechanism? → A: The new versioned unit is named "Corpus" and is the single canonical content mechanism; legacy support, data migration, and backwards compatibility with the prior directory-based corpus ingestion are out of scope for this feature.
- Q: Which content formats must ingestion accept in v1? → A: Any readable UTF-8 text content, extension-agnostic — the encoding/size/readability gate decides acceptance; binary content is rejected.
- Q: What concurrency scale must isolated ingestion support? → A: No fixed numeric target; guarantee isolation and acceptance-serialization correctness at any concurrency the host supports, deferring throughput numbers to planning/load-testing.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Reproducible training from a pinned content version (Priority: P1)

A person preparing a training run selects a specific, frozen version of a corpus and starts training against it. Months later — after the corpus has grown and changed many times — they (or a teammate) re-open that run's record, see exactly which content version it used, and re-run training against the identical content set, producing the same data inputs as the original run.

**Why this priority**: Reproducibility-by-reference is the headline value of the feature. Without the ability to pin and later re-resolve the exact content that fed a training run, experiment results cannot be trusted, compared, or reproduced. This is the foundation every other capability builds on, and it delivers standalone value even if no other story ships.

**Independent Test**: Create a corpus with a known set of entries, freeze it as a version, record that version against a training run, then add and remove entries from the corpus. Re-resolve the run's pinned version and confirm the resolved content matches the original set exactly, unaffected by the later changes.

**Acceptance Scenarios**:

1. **Given** a frozen content version referenced by a completed training run, **When** new content is added to the same corpus afterward, **Then** re-resolving the run's pinned version returns the original content set unchanged.
2. **Given** a training run in progress, **When** the run starts, **Then** the exact content version it consumes is recorded against the run as a durable, human-traceable reference.
3. **Given** a content version that is referenced by at least one training run, **When** routine cleanup of old/unused content occurs, **Then** the referenced version and its content are preserved and never removed.
4. **Given** two training runs that pinned the same content version, **When** their records are compared, **Then** both show an identical content reference.

---

### User Story 2 - Concurrent isolated content injection (Priority: P1)

Multiple independent content-producing systems add new material to the repository at the same time. Each producer works in its own isolated workspace and cannot see, overwrite, or corrupt another producer's in-progress work. When a producer finishes and its content passes all quality checks, the content is folded into the shared, canonical corpus content automatically. Producers that are still working — or whose content failed checks — do not affect the shared corpus content or each other.

**Why this priority**: The repository must support many simultaneous content sources without contention or cross-contamination. Isolation is what makes the canonical corpus content safe to read from (and pin, per US1) even while ingestion is actively happening. This is the second locked decision and is independently valuable: a team could use the repository purely as a safe concurrent-ingestion target.

**Independent Test**: Start two ingestion sessions from two different sources simultaneously, each adding distinct content. Confirm neither session can read or alter the other's staged content, that both can complete independently, and that on successful completion each session's content appears in the shared corpus content without disturbing the other's.

**Acceptance Scenarios**:

1. **Given** two ingestion sessions running concurrently from different sources, **When** both add content, **Then** neither session's staged content is visible to or modifiable by the other until accepted.
2. **Given** an ingestion session whose content passes all quality checks, **When** the session completes, **Then** its content is folded into the shared corpus content automatically without requiring a person to approve the merge.
3. **Given** an ingestion session whose content fails a quality check, **When** the failure occurs, **Then** the content is rejected, the shared corpus content is unchanged, and the specific failures are recorded and surfaced to the operator.
4. **Given** a producer scoped to one source, **When** it attempts to write content outside its own ingestion workspace, **Then** the write is denied.

---

### User Story 3 - Automated quality and safety validation gates (Priority: P1)

As content is ingested, it automatically passes through validation gates before it can join the canonical corpus content. Fast checks run on each batch of incoming content (e.g., readable text encoding, accepted file format, size within bounds, required provenance metadata present, no exact duplicates within the batch). Broader checks run before content joins the shared corpus content (e.g., no exact duplicates across the whole corpus, language is on the allowed list, no sensitive or restricted information, content conforms to the expected shape). Slower, advisory checks (e.g., near-duplicate detection) run after acceptance and raise flags for review without blocking.

**Why this priority**: Quality gates are what make automatic, human-free merging (US2) trustworthy. They prevent malformed, duplicate, unsafe, or non-compliant content from silently entering the data that trains models. Tied to P1 because automatic merge without gates is unsafe.

**Independent Test**: Submit a batch containing one malformed item, one exact duplicate, and one valid item. Confirm the valid item can proceed, the malformed and duplicate items are blocked with clear reasons, and a near-duplicate (but not exact) item is accepted but flagged for later review.

**Acceptance Scenarios**:

1. **Given** an incoming batch containing content with unreadable encoding, **When** the fast per-batch checks run, **Then** the batch is rejected with a reason identifying the offending item.
2. **Given** content missing required provenance metadata (source, license, owning system), **When** the per-batch checks run, **Then** the content is rejected with a reason.
3. **Given** content that exactly duplicates material already in the shared corpus content, **When** the pre-acceptance checks run, **Then** the duplicate is rejected.
4. **Given** content in a language not on the allowed list or containing restricted/sensitive information, **When** the pre-acceptance checks run, **Then** the content is rejected with the matching reason.
5. **Given** content that is a near-duplicate (but not exact) of existing material, **When** it is accepted, **Then** it is admitted into the corpus but flagged by an advisory review process without blocking acceptance.

---

### User Story 4 - Compose and ensemble weighted content versions (Priority: P2)

A curator selects entries drawn from one or more sources, assigns each a sampling weight, previews the resulting mix (e.g., how many tokens or bytes each source contributes), and freezes the selection as a named, promotable content version. The composition is self-describing: the recorded version captures both the exact content snapshot and the weighted recipe, so the same mix can be reproduced later.

**Why this priority**: Composition/ensembling turns raw ingested content into purposeful training datasets. It depends on US1 (versioning) and US2/US3 (a populated, validated corpus) being in place, so it is P2 — high value but not the minimum viable slice.

**Independent Test**: Select entries from two sources, set weights (e.g., 70/30), preview the projected mix, and freeze the version. Re-open the frozen version and confirm the same entries, weights, and recipe are preserved and reproducible.

**Acceptance Scenarios**:

1. **Given** entries from multiple sources, **When** the curator assigns weights and requests a preview, **Then** the system shows the projected contribution (token/byte counts) of each source in the mix.
2. **Given** a previewed composition, **When** the curator freezes it, **Then** a named content version is created that captures both the content snapshot and the weighted recipe.
3. **Given** a frozen composition version, **When** it is re-opened later, **Then** the original entries, weights, and recipe are reproduced exactly.
4. **Given** a frozen composition version, **When** a training run pins it, **Then** the run consumes the entries according to their recorded weights.

---

### User Story 5 - Browse content library, version timeline, and lineage (Priority: P2)

A curator opens a content library view listing all corpora with their status, latest version, size, and source mix. Selecting a corpus shows its version timeline (each version's reference, entry count, promotion tag, and what changed versus the prior version). A lineage view shows, for any version, which sources contributed and which training runs referenced it.

**Why this priority**: Visibility makes the repository usable and auditable. It is P2 because it observes the data created by P1 capabilities; the core value (reproducibility) exists without it, but adoption and trust depend on it.

**Independent Test**: With several corpora and versions present, open the library and confirm each corpus's summary is accurate; open one corpus and confirm its version timeline and per-version diffs are correct; open lineage for a version and confirm it lists the contributing sources and referencing runs.

**Acceptance Scenarios**:

1. **Given** multiple corpora, **When** the curator opens the library, **Then** each corpus shows its status, latest version, size, and source mix.
2. **Given** a corpus with multiple versions, **When** the curator opens its timeline, **Then** each version shows its reference, entry count, promotion tag, and difference from the prior version.
3. **Given** a content version referenced by training runs, **When** the curator opens its lineage, **Then** the contributing sources and the referencing runs are listed.

---

### User Story 6 - Import content from external and local sources (Priority: P2)

An operator starts an import job that pulls content into the repository from a configured local or external source, then watches the job's progress to completion (or failure). Imported content flows through the same ingestion and validation path as any other injected content.

**Why this priority**: Import is a key on-ramp for populating the repository but reuses the injection and validation machinery from US2/US3, so it is P2.

**Independent Test**: Configure and start an import job against a known source, watch its progress update live to completion, and confirm the imported content underwent the standard validation gates and appears in the corpus.

**Acceptance Scenarios**:

1. **Given** a configured import source, **When** the operator starts an import job, **Then** the job begins and reports live progress.
2. **Given** a running import job, **When** it completes, **Then** the imported content has passed the standard validation gates and is present in the corpus.
3. **Given** a running import job, **When** it fails, **Then** the failure and its reason are recorded and surfaced to the operator.

---

### User Story 7 - Checkout locks for safe manual curation (Priority: P3)

When a curator begins editing or composing against a particular scope, they can acquire an advisory checkout lock that signals to others that the scope is in active use, including who holds it and since when. They can release the lock when done; others can see active locks on a board.

**Why this priority**: Locks reduce accidental concurrent-edit collisions in the management plane. It is P3 because the underlying isolation (US2) already protects the canonical corpus content; locks are a coordination convenience for human curators.

**Independent Test**: Acquire a lock on a scope, confirm it appears on the checkout board with holder and timestamp, confirm a second curator sees it as held, then release it and confirm it clears.

**Acceptance Scenarios**:

1. **Given** an available scope, **When** a curator acquires a lock, **Then** the lock appears on the checkout board with scope, holder, and acquisition time.
2. **Given** a held lock, **When** another curator views the board, **Then** they see the scope as held and by whom.
3. **Given** a held lock, **When** the holder releases it, **Then** the scope becomes available and the lock clears from the board.

---

### User Story 8 - Transparent zero-config operation for local users (Priority: P1)

A person running the product on their own machine uses every content-repository capability — pinning versions, ingesting, composing, browsing — without ever configuring, starting, stopping, or even knowing about the supporting background services that make versioning and storage work. Those services come up automatically when the product starts and shut down when it stops, exactly the way experiment tracking already does today. To the local user, the content repository is simply a built-in feature of the product.

**Why this priority**: This is how the entire feature is consumed in the local mode that the product targets first. If a local user has to install, configure, or manage a separate service, the feature fails its core promise of a self-contained, just-works workbench. It is P1 because every other story is consumed through this mode locally, and it must match the existing "managed sidecar" experience of the current experiment-tracking service.

**Independent Test**: On a clean local install, start the product and exercise the content-repository features end-to-end (create a corpus, ingest content, freeze a version, train against it) without performing any service setup or configuration, and without the supporting services being surfaced to the user. Stop the product and confirm the supporting services are cleanly shut down.

**Acceptance Scenarios**:

1. **Given** a clean local install, **When** the user starts the product, **Then** all supporting services required by the content repository start automatically without any user action or configuration.
2. **Given** a running local product, **When** the user uses content-repository features, **Then** they are not required to know about, configure, or manage any supporting background service.
3. **Given** a running local product, **When** the user stops the product, **Then** the supporting services are shut down cleanly as part of the same lifecycle.
4. **Given** a local install, **When** the user opens the product for the first time, **Then** the content repository is usable out of the box with sensible defaults (no external accounts, credentials, or services to provision).

---

### User Story 9 - Full visibility of the managed component for SaaS users (Priority: P2)

A person using the hosted (SaaS) offering sees the content repository presented as a first-class, fully managed component alongside the product's other configuration and services. They can view its status and health in the same place they observe the rest of the managed services, with the operational details surfaced (rather than hidden) appropriate to a managed-service context.

**Why this priority**: In the hosted context, transparency and observability of managed components is expected and builds operator trust. It is P2 because it concerns how an existing capability is surfaced in the SaaS mode rather than introducing new core content functionality; the local experience (US8) is the first-shipped mode.

**Independent Test**: In the SaaS configuration, open the services/configuration surface and confirm the content repository appears as a managed component with its status and health visible alongside the other managed services.

**Acceptance Scenarios**:

1. **Given** the hosted offering, **When** a SaaS user opens the services/configuration surface, **Then** the content repository appears as a managed component alongside the other services.
2. **Given** the hosted offering, **When** a SaaS user views the managed component, **Then** its status and health are visible in the same place as the product's other managed services.
3. **Given** the local offering, **When** a local user opens the product, **Then** the supporting services remain hidden (contrast with the SaaS surfacing), preserving the zero-config local experience.

---

### Edge Cases

- **Concurrent acceptance race**: Two ingestion sessions independently pass their gates and attempt to fold into the shared corpus content at the same instant — the system must serialize acceptance so the canonical corpus content remains consistent and both contributions are preserved.
- **Referenced version cleanup**: A cleanup process runs while a version is referenced by a run — referenced versions must never be removed (see US1 AS3). Conversely, abandoned/failed ingestion workspaces are retained for a defined forensic window, then cleaned up.
- **Gate timeout/unavailability**: A validation gate is slow or temporarily unavailable during a pre-acceptance check — the operation must fail closed (content is not accepted) rather than admit unvalidated content.
- **Empty or zero-weight composition**: A curator freezes a composition with no entries, or assigns a zero weight to every entry — the system must reject or clearly warn rather than create an unusable version.
- **Provenance with disallowed license**: Incoming content references a license that is not on the approved list — the content is rejected with a clear reason.
- **Producer writing outside its scope**: A scoped producer attempts to write outside its assigned ingestion workspace or to fold content into the canonical corpus content directly — the action is denied (see US2 AS4).
- **Mistaken merge recovery**: Bad content is automatically merged because it passed gates that should have caught it — a curator must be able to revert the canonical corpus content to a prior known-good state (time-travel safety net), since there is no per-merge human approval step.
- **Stale lock**: A curator acquires a lock and never releases it — other curators must still be able to see the lock's age and holder; lock holding is advisory and does not hard-block the protected canonical corpus content.

## Requirements *(mandatory)*

### Functional Requirements

**Versioning & reproducibility**

- **FR-001**: System MUST allow a corpus to be frozen into an immutable, named version that captures the exact set of content entries at a point in time.
- **FR-002**: System MUST record, against each training run, a durable reference to the exact content version the run consumed.
- **FR-003**: System MUST be able to resolve a recorded content version back to the identical set of content entries at any later time, regardless of subsequent changes to the corpus.
- **FR-004**: System MUST guarantee that frozen versions are immutable — once created, their content set cannot be altered.
- **FR-005**: Training runs MUST consume content via a pinned version reference and MUST NOT depend on the mutable "latest" state of a corpus.

**Concurrent isolated ingestion**

- **FR-006**: System MUST allow multiple content producers to ingest content simultaneously, each in an isolated workspace that is not visible to or modifiable by other producers until the content is accepted.
- **FR-007**: System MUST scope each producer's write access to its own ingestion workspace and MUST deny writes outside that scope.
- **FR-008**: System MUST prevent any producer from writing directly to the canonical (shared) corpus content; content MUST enter the canonical corpus content only through the validated acceptance flow.
- **FR-009**: System MUST automatically fold a producer's content into the canonical corpus content when all validation gates pass, without requiring per-merge human approval.
- **FR-010**: System MUST serialize concurrent acceptances so the canonical corpus content remains consistent when multiple sessions complete simultaneously. Isolation and acceptance-serialization MUST remain correct at any concurrency level the host supports; no fixed numeric concurrency target is imposed at the specification level (throughput targets, if any, are determined during planning/load-testing).
- **FR-011**: System MUST provide a way to revert the canonical corpus content to a prior known-good state as a safety net for content that was accepted in error.

**Validation gates**

- **FR-012**: System MUST run fast per-batch validation on incoming content covering at minimum: readable UTF-8 text encoding, size within bounds, presence of required provenance metadata (source, license, owning system), and absence of exact duplicates within the batch. Acceptance is extension-agnostic — any readable UTF-8 text content is accepted regardless of file extension, and content that is not readable UTF-8 text (e.g., binary) is rejected. This per-batch validation MUST return its pass/fail outcome within ~5 seconds for a typical batch.
- **FR-013**: System MUST run pre-acceptance validation before content joins the canonical corpus content covering at minimum: absence of exact duplicates across the whole corpus, language on the allowed list, and absence of restricted/sensitive information. For the v1 default (free-form UTF-8 text), no structural "shape" gate applies beyond encoding/size/dedup/language/sensitive-info; a structural-conformance gate applies ONLY to content that declares a structured format (deferred — not part of the text-only v1 scope). This pre-acceptance (cross-corpus) validation MUST return its pass/fail outcome within ~30 seconds.
- **FR-014**: System MUST reject content that fails any blocking validation gate, leave the canonical corpus content unchanged, and record the specific failure reasons in a form that can be surfaced to the operator.
- **FR-015**: System MUST run advisory (non-blocking) checks — including near-duplicate detection — after acceptance, raising flags for review without blocking or reverting the accepted content.
- **FR-016**: System MUST fail closed (reject rather than admit) when a blocking validation gate is unavailable or times out.
- **FR-017**: System MUST reject content whose declared license is not on the approved license list.

**Composition & ensembling**

- **FR-018**: System MUST allow a curator to select content entries from one or more sources and assign a sampling weight to each.
- **FR-019**: System MUST provide a preview of a proposed composition showing each source's projected contribution (e.g., token/byte counts) before the version is frozen.
- **FR-020**: System MUST freeze a composition into a named version that captures both the immutable content snapshot and the weighted recipe, such that the mix is reproducible.
- **FR-021**: System MUST apply recorded entry weights when a composed version is consumed by a training run.
- **FR-022**: System MUST reject or clearly warn against compositions that are empty or that would yield no usable content (e.g., all-zero weights).

**Promotion, retention & lineage**

- **FR-023**: System MUST allow a frozen version to be promoted with a stable, human-readable tag.
- **FR-024**: System MUST never remove any content version that is referenced by a training run during routine cleanup.
- **FR-025**: System MUST retain failed or abandoned ingestion workspaces for a defined forensic window before cleaning them up, and MUST remove successfully accepted ingestion workspaces after acceptance.
- **FR-026**: System MUST record, for each version, which sources contributed and which training runs referenced it (lineage).
- **FR-026a**: After content is accepted into the canonical corpus content, System MUST record acceptance statistics and the per-event lineage that complements the per-version lineage of FR-026, and MUST refresh the corpus's derived training-ready state (e.g., re-chunk/re-tokenize) so that subsequent version freezes and training runs reflect the newly accepted content. (This is the post-acceptance superset of FR-026's per-version lineage record.)

**Visibility (management surface)**

- **FR-027**: System MUST present a content library listing all corpora with status, latest version, size, and source mix.
- **FR-028**: System MUST present, per corpus, a version timeline showing each version's reference, entry count, promotion tag, and difference from the prior version.
- **FR-029**: System MUST present live status of in-progress ingestion sessions, including source, status, streaming validation results, and acceptance events.
- **FR-030**: System MUST present live progress of import jobs.
- **FR-031**: System MUST present a lineage view per version (contributing sources and referencing runs).

**Import**

- **FR-032**: Users MUST be able to start an import job from a configured local or external source and monitor its progress to completion or failure.
- **FR-033**: System MUST route imported content through the same validation gates as any other injected content.

**Checkout locks**

- **FR-034**: Users MUST be able to acquire and release an advisory checkout lock on a scope, with the lock recording its scope, holder, and acquisition time.
- **FR-035**: System MUST present active locks on a board visible to all curators.

**Access control**

- **FR-036**: System MUST enforce separation between data-access permissions (who may read/write which content) and management-action permissions (who may rename, tag, compose, promote, or acquire/release locks). **Mode scoping**: in local single-user mode this separation is satisfied trivially (the single local operator holds both planes; management endpoints remain available to that operator) and the implementation MUST expose a clear seam where multi-principal enforcement is injected; meaningful multi-principal separation is enforced in the hosted (SaaS) mode.
- **FR-037**: System MUST restrict back-office administration (access-control configuration and raw-record inspection) to authorized administrators only. **Mode scoping**: this applies wherever a back-office surface is present; the back-office surface is part of the hosted (SaaS) delivery and is therefore deferred (no back-office is exposed in local mode, so there is nothing unauthorized to reach).

**Operating modes & service lifecycle**

> **Mode-scoping note**: If the local implementation runs **no** separate supporting
> background services (i.e., the content repository is built into the application
> process), then FR-039, FR-043, and FR-044 are satisfied **vacuously** in local mode —
> there is no service to start/stop, surface health for, or expose controls of. These
> requirements bind meaningfully only where supporting services exist (the hosted/SaaS
> mode, or any future local implementation that introduces a managed sidecar). The
> requirements are written to hold in **either** case.

- **FR-039**: In local mode, System MUST start and stop all supporting services the content repository depends on automatically as part of the product's own lifecycle, without requiring the user to install, configure, start, or stop them — matching the managed-sidecar experience of the existing experiment-tracking service. (Vacuously satisfied when no such services exist locally — see mode-scoping note.)
- **FR-040**: In local mode, System MUST NOT require the user to be aware of, or interact with, any supporting background service in order to use content-repository capabilities; the repository MUST be usable out of the box with sensible defaults and no external accounts, credentials, or services to provision.
- **FR-041**: In the hosted (SaaS) mode, System MUST present the content repository as a fully managed component alongside the product's other configuration and services, with its status and health visible to SaaS users.
- **FR-042**: System MUST keep the content-repository capabilities (versioning, ingestion, validation, composition, lineage, visibility) behaviorally identical across local and hosted modes; only the deployment and the degree of operational visibility of the supporting services differ.
- **FR-043**: System MUST surface the operational health of the content repository's supporting services in a manner appropriate to each mode (hidden/transparent locally; visible as a managed component in SaaS), and MUST degrade gracefully with a clear message if a required supporting service is unavailable.
- **FR-044**: System MUST NOT expose, in local mode, any configuration, credentials, or service-management controls for the supporting services to the end user.

**Canonical content unit (clean implementation, no legacy)**

- **FR-038**: The versioned content unit delivered by this feature MUST be named "Corpus" and MUST be the single, canonical mechanism for managing training content going forward.
- **FR-038a**: Legacy support, data migration, and backwards compatibility with any prior directory-based corpus ingestion are OUT OF SCOPE for this feature; the System is NOT required to keep a prior mechanism functional, migrate its data, or preserve compatibility with it.
- **FR-038b**: Where any prior directory-based mechanism remains present in the product, it MUST be labeled "Directory Corpus (deprecated)" to distinguish it from the canonical Corpus; its continued operation is not a requirement of this feature.
- **FR-038c**: New content-management functionality MUST be delivered exclusively through the canonical Corpus.

### Key Entities *(include if feature involves data)*

- **Source**: A registered origin of content (an automated injector, an importer, or a manual contributor). Identifies and scopes who/what produced content; appears in content provenance and in producer access scoping.
- **Corpus**: A named, evolving body of related content — the single canonical content unit. Carries its chunking configuration (strategy and parameters) applied when resolving content for training, a lifecycle status (e.g., draft, active, archived), a current (canonical) state, and a history of frozen versions. The unit a curator organizes and a consumer trains against.
- **Content Version**: A frozen, immutable, reproducible snapshot of a corpus at a point in time — an exact set of entries plus (for compositions) a weighted recipe. The unit a training run pins for reproducibility.
- **Entry**: A single piece of content within a version, optionally carrying a sampling weight and a reference to its originating source.
- **Promotion Tag**: A stable, human-readable label attached to a version marking it as promoted and protecting it from cleanup.
- **Ingestion Session**: An in-progress, isolated workspace where a producer stages content for validation and acceptance. Has a status (open, validating, accepted [merged], failed) and records any validation problems.
- **Import Job**: A configured, monitored task that pulls content from a local or external source into the repository through the ingestion path.
- **Validation Result / Problem Record**: The recorded outcome of a validation gate — pass, or fail with specific reasons — surfaced to operators.
- **Checkout Lock**: An advisory record that a scope is in active use, capturing scope, holder, and timestamps.
- **Lineage Record**: The association between a version, its contributing sources, and the training runs that referenced it.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of training runs that pin a content version can re-resolve the identical content set at any later time, even after the underlying corpus has changed.
- **SC-002**: Content referenced by any training run is preserved through 100% of routine cleanup cycles (zero referenced-content losses).
- **SC-003**: Multiple producers can ingest content concurrently with zero cross-contamination — no producer's in-progress content is ever visible in or altered by another producer's session — at any concurrency level the host supports.
- **SC-004**: 100% of content that fails a blocking validation gate is kept out of the canonical corpus content (zero invalid items admitted through blocking gates).
- **SC-005**: Content that passes all gates is folded into the canonical corpus content automatically, with no manual approval step required, in the common case.
- **SC-006**: A curator can compose a weighted multi-source version, preview its mix, and freeze it as a reproducible version, and the frozen mix reproduces identically on re-open (100% recipe fidelity).
- **SC-007**: For any content version, a curator can identify its contributing sources and every training run that referenced it (complete lineage coverage).
- **SC-008**: Operators can observe ingestion and import activity as it happens, seeing validation outcomes and completion/failure for in-flight work.
- **SC-009**: A curator can revert the canonical corpus content to a prior known-good state after an erroneous acceptance, restoring it without data loss to earlier versions.
- **SC-010**: A local user can complete the full content-repository workflow (create → ingest → freeze → train) on a clean install with zero configuration steps and zero interactions with any supporting background service.
- **SC-011**: The same content-repository capabilities are available in both local and hosted modes, with the only user-visible difference being that hosted mode surfaces the component's managed status/health while local mode keeps supporting services hidden.
- **SC-012**: Producers receive per-batch validation feedback within ~5 seconds for a typical batch, and cross-corpus pre-acceptance validation completes within ~30 seconds, for the common case. ("Typical batch" reference for verification: up to ~100 text entries totaling ≤ ~10 MB; targets are measured against this reference on commodity local hardware.)

## Assumptions

- **Content type**: The initial scope is text content — specifically, any readable UTF-8 text content, accepted extension-agnostically (the encoding/size/readability gate decides; document-shaping is handled by the existing chunking strategies). Binary/multimodal content (images, audio, video) is rejected by the gate and reuses the same versioning, ingestion, validation, composition, and lineage model as a later expansion, not part of this version.
- **Merge policy**: Ingestion lanes auto-merge into the canonical corpus content on all-green validation with no per-merge human approval; revert (time-travel) is the safety net. An approval queue for untrusted external producers is a future addition, not built now.
- **Duplicate detection**: Exact-duplicate detection runs as a fast blocking gate (per-batch and across-corpus); near-duplicate detection runs as an asynchronous, advisory, non-blocking process that flags rather than rejects.
- **Retention**: Successfully accepted ingestion workspaces are removed after acceptance. Failed/abandoned workspaces are retained for a defined forensic window (assumed ~30 days) and then cleaned up. Versions referenced by training runs are never cleaned up.
- **Reproducibility anchor**: The recorded content reference is the authoritative reproducibility anchor for a run; a portable, self-describing recipe accompanies composed versions so they remain reproducible.
- **Access control planes**: Two permission planes exist — one governing data access (read/write scoping by source) and one governing management actions (rename, tag, compose, promote, lock). Back-office administration is restricted to administrators.
- **Provenance metadata**: All ingested content is expected to carry provenance metadata (source, license, owning system); content lacking it is rejected. The approved-license list governs acceptable licenses and reuses the existing governance license catalog.
- **Existing governance reuse**: Sensitive-information scanning, license approval, and audit/lineage recording build on the project's existing data-governance capabilities rather than introducing a parallel mechanism.
- **Management surface**: The management and monitoring screens are part of the existing application's primary experience; a separate, lightly-branded back-office surface serves administrators for access-control configuration and raw-record inspection.
- **Operating modes**: The product runs in a local mode (self-contained, single-machine) and a hosted (SaaS) mode. In local mode, supporting services for the content repository are managed automatically and transparently as background services — the same way the existing experiment-tracking service is supervised today — and are never surfaced to the user. In hosted mode, the content repository is a fully managed component whose status and health are visible alongside the product's other managed services. The underlying content capabilities are identical across modes; this aligns with the project's established three-mode operating model and its storage/service abstraction approach.
- **Mode parity**: This specification does not require the hosted (SaaS) deployment to be built in the same delivery as the local mode; it requires that the capability design not preclude the hosted managed-component presentation, and that local mode ship with the transparent, zero-config experience.
- **Canonical content unit (clean implementation)**: The versioned "Corpus" is the single, canonical content unit. This feature is a clean implementation: legacy support, data migration, and backwards compatibility with any prior directory-based corpus ingestion are explicitly out of scope. Any prior directory-based mechanism that remains is labeled "Directory Corpus (deprecated)" but its continued operation is not a requirement here; whether and when it is removed is a separate, future decision.
- **Deployment topology vs. operating modes**: The source design draft describes one server-style deployment (a versioned object store plus relational metadata behind the application, orchestrated on a cluster). In this specification that corresponds to the hosted (SaaS) mode; local mode runs the equivalent supporting services as transparent, automatically-managed sidecars (per the operating-modes assumption). All capability requirements are deployment-agnostic — the substrate and metadata store may differ by mode without changing behavior.
- **Post-acceptance automation**: After acceptance, the corpus's derived training-ready state is refreshed (re-tokenization) and acceptance stats/lineage are recorded (FR-026a). Automatically triggering a training run upon acceptance is optional and out of scope for this version.
- **Pinning granularity**: A training run pins a frozen content version; every run-referenced version is retention-protected regardless of whether it also carries a promotion tag (a promotion tag is an additional human-readable, promotable label, not a precondition for pinning).
