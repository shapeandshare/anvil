---
title: 013 Responsible Data Governance - spec
type: spec
tags:
  - type/spec
spec-refs:
  - docs/vault/Specs/013 Responsible Data Governance/
related:
  - '[[013 Responsible Data Governance]]'
created: ~
updated: ~
---
# Feature Specification: Responsible Sample Data & Universal No-Harm Governance

**Feature Branch**: `013-responsible-data-governance`
**Created**: 2026-06-19
**Status**: Draft
**Input**: User description: "i want to include sample data in the application but we need to do so legally, ethically, and respectfully, and in an auditable manner. we also want the usage of the system to be held to this same univsal no-harm stance"

## Clarifications

### Session 2026-06-19

- Q: How should the license requirement apply to user-supplied data vs. bundled sample data? → A: User-supplied data may use a self-declared "own/private/proprietary" provenance category that satisfies the gate without an approved redistribution license; the approved-license-list requirement applies only to bundled sample data the project itself redistributes.
- Q: What level of tamper-evidence must the audit trail provide? → A: Cryptographic hash-chaining — each audit entry includes a hash of the previous entry so any alteration of the trail is detectable.
- Q: How should the acceptable-use gate determine that content is prohibited? → A: Affirmation/declaration only — the gate relies on the user's no-harm affirmation and explicit declarations plus rejection of empty/unparseable input; no automated content inspection (keyword, PII, or ML scanning) is in scope.
- Q: What licenses should the initial approved-license catalog (for bundled sample data) contain? → A: A broad OSI/Creative-Commons set — e.g., Public Domain, CC0, MIT, BSD, Apache-2.0, CC-BY, CC-BY-SA, plus the project's own Generated/Original content; maintainer-extendable.
- Q: What retention policy should govern the audit trail? → A: Retain indefinitely with no automatic pruning, preserving the hash chain; any archival/reset is an explicit, audited maintainer action.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Every bundled sample carries verifiable, lawful provenance (Priority: P1)

A maintainer adds (or audits) the sample datasets and corpora that ship with the application. Each sample must declare where it came from, the license under which it may be redistributed, and the attribution it requires. The application refuses to ship — or surface to end users — any sample that lacks a complete, recognized provenance record. When the application first runs and seeds its sample data, every seeded item is accompanied by its source, license, and attribution, all stored so they can be reviewed later without consulting external documents.

**Why this priority**: This is the legal and ethical foundation. Shipping sample data without verifiable licensing exposes the project and its users to copyright/redistribution risk. Without it, no other governance guarantee is meaningful. It is independently valuable: even with nothing else built, the project gains a defensible, auditable bill-of-materials for its bundled data.

**Independent Test**: Inspect the seeded sample data after a fresh install and confirm every sample exposes a complete provenance record (source, license, attribution, classification as bundled-sample vs. user-supplied). Introduce a sample missing a license and confirm the system declines to seed/surface it and reports why.

**Acceptance Scenarios**:

1. **Given** a fresh installation, **When** the application seeds its bundled sample data, **Then** every seeded dataset and corpus has a stored, machine-readable provenance record containing at minimum a source description, a recognized license identifier, required attribution text (if any), and a flag marking it as bundled sample data.
2. **Given** a candidate bundled sample whose license is missing, empty, or not on the approved-license list, **When** seeding runs, **Then** that sample is not seeded and the omission is recorded with a clear reason.
3. **Given** seeded sample data, **When** a user views a sample dataset or corpus, **Then** its source, license, and any required attribution are visible to the user.
4. **Given** a license that requires attribution, **When** the sample is displayed or exported, **Then** the required attribution accompanies the content.

---

### User Story 2 - Every consequential action is auditable (Priority: P1)

A reviewer (maintainer, auditor, or the user themselves) needs to reconstruct what data entered the system, when, by what means, and what happened to it. The system records an immutable, human-readable trail of consequential events — sample data being seeded, user data being uploaded or imported, data being curated, data being deleted or taken down, and acceptable-use decisions (acceptances and rejections). Each entry captures what happened, to which entity, when, by whom (or by which automated process), and the relevant parameters, without storing more sensitive content than necessary.

**Why this priority**: "Auditable" is an explicit, first-class requirement in the request. Today the only lifecycle signal is fire-and-forget experiment-tracking runs that silently drop failures and carry no actor or reason. An audit trail is independently valuable and testable on its own.

**Independent Test**: Perform a representative set of actions (seed, upload, curate, delete, policy-reject) and confirm each produces a durable, ordered, tamper-evident audit entry with action type, target, timestamp, actor/source, and outcome — retrievable and readable after the fact.

**Acceptance Scenarios**:

1. **Given** the system seeds bundled sample data, **When** seeding completes, **Then** an audit entry exists for each seeded item recording the action, target, timestamp, source (bundled sample), and provenance summary.
2. **Given** a user uploads or imports data, **When** the upload completes (or is rejected), **Then** an audit entry records the action, the dataset/corpus target, timestamp, the acting user/session, the declared provenance, and the accept/reject outcome with reason.
3. **Given** a user curates data (edit, deduplicate, filter, remove samples), **When** the operation finishes, **Then** an audit entry records the operation type, target, parameters, and before/after counts.
4. **Given** data is deleted or taken down, **When** the deletion completes, **Then** an audit entry records the deletion, its reason, and confirmation that associated stored artifacts were removed (no orphaned content).
5. **Given** an audit trail exists, **When** a reviewer queries it, **Then** entries are returned in chronological order and cannot be silently altered or deleted through normal application use.

---

### User Story 3 - Acceptable-use gate on all data entering the system (Priority: P1)

A user uploads or imports their own data, or pastes content directly. Before the data is accepted, the system requires the user to declare the data's provenance and license, and affirm that the content and intended use comply with the project's no-harm acceptable-use policy. Submissions that fail the policy gate — missing/disallowed license, missing required affirmation, or content flagged as prohibited — are rejected with a clear, respectful explanation and recorded in the audit trail. Accepted submissions carry their declared provenance forward.

**Why this priority**: This extends the legal/ethical/auditable guarantees from bundled sample data (Story 1) to all data flowing through the system, fulfilling the "usage held to the same universal no-harm stance" clause. It depends conceptually on Stories 1 and 2 (it reuses the provenance model and the audit trail) but delivers the distinct, user-facing enforcement that turns policy into practice.

**Independent Test**: Attempt an upload without a license declaration and confirm rejection with explanation; attempt an upload with a prohibited-content declaration and confirm rejection; complete a compliant upload and confirm it is accepted, carries provenance, and is recorded in the audit trail.

**Acceptance Scenarios**:

1. **Given** a user begins an upload/import/paste, **When** they submit, **Then** they must provide a source declaration, a recognized license, and an affirmation of acceptable-use compliance before the data is accepted.
2. **Given** a submission missing a license, an unrecognized license, or the acceptable-use affirmation, **When** submitted, **Then** the system rejects it with a clear, respectful explanation and records the rejection in the audit trail.
3. **Given** a compliant submission, **When** accepted, **Then** the resulting dataset/corpus stores the declared provenance and is recorded in the audit trail.
4. **Given** the acceptable-use policy, **When** a user accesses the data-entry surface, **Then** the policy (the no-harm stance and prohibited uses) is presented or clearly linked before submission.

---

### User Story 4 - Codified universal no-harm stance & takedown (Priority: P2)

The project documents and exposes a single, universal "no-harm" governance principle that applies to both the data the system ships and the way the system is used. A user, maintainer, or affected third party can find the acceptable-use policy, understand prohibited uses, and request takedown of specific data. A takedown request is honored by removing the data and its stored artifacts and recording the action in the audit trail.

**Why this priority**: This makes the no-harm stance explicit, discoverable, and actionable rather than implicit. It is lower priority than P1 stories because the enforcement mechanisms (provenance, audit, upload gate) deliver the core protection; this story formalizes and operationalizes the principle and provides the remediation path.

**Independent Test**: Locate the published acceptable-use / no-harm policy from within the application; submit a takedown request for a specific dataset; confirm the data and its artifacts are removed and the action is audited.

**Acceptance Scenarios**:

1. **Given** the application, **When** a user looks for governance terms, **Then** a single acceptable-use / no-harm policy is discoverable and states that it applies equally to bundled data, user data, and system usage.
2. **Given** a request to remove specific data, **When** the takedown is processed, **Then** the data record and all associated stored artifacts are removed and an audit entry records the takedown and its reason.
3. **Given** a deletion or takedown, **When** it completes, **Then** no orphaned content artifacts remain in storage for that item.

---

### Edge Cases

- **Sample with partial provenance**: A bundled sample declares a source but no license (or an unrecognized license). The system MUST NOT seed or surface it and MUST record the omission with a reason.
- **License requiring attribution at point of use**: When sample content is displayed, exported, or used to train, the required attribution MUST travel with it.
- **Duplicate / re-seeding**: When seeding runs again over already-seeded data, provenance MUST NOT be silently overwritten, and re-seeding MUST NOT create duplicate audit noise that obscures the original record.
- **Audit-write failure**: If a consequential action cannot be reliably recorded in the audit trail, the system MUST surface the failure rather than silently proceed as if it were audited.
- **Deletion leaving artifacts**: Deleting a dataset MUST also remove its stored content artifacts; partial deletion (DB record gone, files orphaned) is a defect this feature MUST close.
- **User declares disallowed content**: An upload accompanied by an affirmation that the content is prohibited (or a license that forbids redistribution) MUST be rejected with explanation.
- **Empty or unparseable upload**: Rejected with a clear message and audited as a rejection.
- **Provenance for derived data**: When a user clones, forks, or curates an existing dataset, the new artifact MUST carry forward (or clearly reference) the provenance of its parent.
- **Bundled data is read-only**: Bundled sample provenance MUST remain accurate even though the underlying files reside in a read-only location after installation.

## Requirements *(mandatory)*

### Functional Requirements

#### Provenance & Sample Data

- **FR-001**: System MUST store, for every dataset and corpus, a machine-readable provenance record containing at minimum: a source description, a license identifier, required attribution text (may be empty when the license requires none), and a classification distinguishing bundled sample data from user-supplied data.
- **FR-002**: System MUST maintain an explicit list of approved/recognized licenses under which **bundled sample data** may be accepted and redistributed. This approved-license requirement applies to bundled sample data only. The catalog MUST be seeded with a broad OSI/Creative-Commons set — at minimum Public Domain, CC0, MIT, BSD, Apache-2.0, CC-BY, CC-BY-SA, and the project's own Generated/Original content — and MUST be extendable by maintainers. Licenses that require attribution (e.g., CC-BY, CC-BY-SA) MUST be marked as such so attribution is carried per FR-006.
- **FR-003**: System MUST refuse to seed or surface any bundled sample whose provenance is incomplete or whose license is not on the approved list, and MUST record each such refusal with a reason.
- **FR-004**: System MUST populate provenance from an authoritative, maintained source-of-truth for bundled samples (rather than leaving it as documentation that is never enforced).
- **FR-005**: System MUST display each dataset's and corpus's source, license, and required attribution to users viewing that data.
- **FR-006**: System MUST carry required attribution alongside sample content when it is displayed, exported, or used for training.
- **FR-007**: When data is derived from existing data (clone, fork, curate), System MUST carry forward or reference the parent's provenance to the derived artifact.

#### Audit Trail

- **FR-008**: System MUST record an audit entry for every consequential data event: sample seeding, user upload/import, curation operations, deletion, takedown, and acceptable-use accept/reject decisions.
- **FR-009**: Each audit entry MUST capture, at minimum: the action type, the target entity (type and identifier), a timestamp, the actor or originating process, the outcome, and the relevant parameters/reason.
- **FR-010**: The audit trail MUST be durable and tamper-evident via cryptographic hash-chaining — each entry MUST include a hash of the preceding entry such that any insertion, alteration, or removal of an entry is detectable by recomputing the chain. Entries MUST NOT be silently altered or removed through normal application use, and MUST remain readable/retrievable after the fact.
- **FR-011**: System MUST surface (not silently swallow) any failure to record a required audit entry for a consequential action.
- **FR-012**: System MUST allow a reviewer to retrieve audit entries in chronological order, filterable by target entity and/or action type.
- **FR-013**: Audit entries MUST avoid storing more sensitive raw content than necessary to make the action reconstructable (e.g., reference identifiers and summaries rather than full content bodies where a reference suffices).
- **FR-023**: The audit trail MUST be retained indefinitely with no automatic pruning, preserving the integrity of the hash chain. Any archival or reset of the trail MUST be an explicit maintainer action that is itself recorded (e.g., as a chain checkpoint/closure event).

#### Acceptable-Use Gate (No-Harm Stance on Usage)

- **FR-014**: System MUST require, for all data entering the system via upload/import/paste, a declared source, a license declaration, and an affirmation of acceptable-use (no-harm) compliance before acceptance. The license declaration MAY be a self-declared "own/private/proprietary" provenance category (which does not need to appear on the approved-license list); the approved-license-list requirement (FR-002) applies only to bundled sample data.
- **FR-015**: System MUST reject any data submission that lacks a license declaration (either an approved license or the self-declared own-content category), lacks the required acceptable-use affirmation, is declared by the submitter as prohibited content, or is empty/unparseable, and MUST return a clear, respectful explanation. The system determines prohibition by submitter declaration/affirmation only and MUST NOT perform automated content inspection (keyword, PII, or ML-based scanning) within this feature's scope.
- **FR-016**: System MUST record every acceptance and rejection decision in the audit trail with its reason.
- **FR-017**: System MUST present or clearly link the acceptable-use / no-harm policy at the point of data entry, before submission.
- **FR-018**: The acceptable-use policy MUST state that the same no-harm stance applies uniformly to bundled sample data, user-supplied data, and use of the system itself.

#### Governance Document & Takedown

- **FR-019**: System MUST publish a single, discoverable acceptable-use / no-harm governance policy describing prohibited uses and the universal stance. (Distinct from FR-017: FR-019 is the standalone published policy page; FR-017 is the link/summary surfaced at the point of data entry.)
- **FR-020**: System MUST provide a mechanism to request and execute takedown/removal of specific data.
- **FR-021**: When data is deleted or taken down, System MUST remove both the data record and all associated stored content artifacts, leaving no orphaned artifacts, and MUST record the action in the audit trail.
- **FR-022**: System MUST preserve existing protections that prevent accidental deletion of bundled sample data without an explicit override.

### Key Entities *(include if feature involves data)*

- **Provenance Record**: The lawful/ethical origin metadata attached to a dataset or corpus. Attributes: source description, license identifier (an approved-license identifier OR the special "own/private/proprietary" own-content category for user-supplied data), required attribution, origin classification (bundled-sample vs. user-supplied), reference to parent provenance when derived. Relationship: one-to-one with each dataset/corpus.
- **License Catalog**: The set of recognized/approved licenses governing what **bundled sample data** may be accepted and redistributed. Attributes: license identifier, whether attribution is required, redistribution allowance. Relationship: referenced by every bundled-sample Provenance Record; user-supplied data may instead reference the own-content category.
- **Audit Entry**: An immutable record of a consequential event, linked into a verifiable hash chain. Attributes: action type, target type, target identifier, timestamp, actor/source, outcome, parameters/reason, hash of the preceding entry, and this entry's own hash. Relationship: many-to-one with the target entity (dataset, corpus, sample, or policy decision); each entry chains to its predecessor.
- **Acceptable-Use Affirmation**: The user's declaration, captured at data-entry time, that a submission complies with the no-harm policy. Attributes: affirmation outcome, declared source, declared license, decision (accept/reject), reason. Relationship: associated with an upload/import event and its resulting dataset/corpus.
- **Acceptable-Use / No-Harm Policy**: The single governing document stating prohibited uses and the universal stance. Relationship: referenced by the data-entry surface and the audit decisions.
- **Takedown Request**: A request to remove specific data. Attributes: target entity, reason, requester/source, resolution. Relationship: resolves to a deletion action recorded in the audit trail.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of sample datasets and corpora that ship with the application expose a complete provenance record (source, license, attribution) that a reviewer can inspect without consulting external documents.
- **SC-002**: 100% of bundled samples carry a license drawn from the approved-license list; any sample failing this check is not surfaced to users and the omission is recorded.
- **SC-003**: 100% of consequential data events (seed, upload, import, curate, delete, takedown, policy decision) produce a retrievable audit entry; a reviewer can reconstruct the full lifecycle of any dataset from the audit trail alone.
- **SC-004**: 100% of data submissions are evaluated against the acceptable-use gate before acceptance; no data enters the system without a recorded provenance declaration and acceptable-use decision.
- **SC-005**: 0 orphaned content artifacts remain in storage after a dataset deletion or takedown (every deleted record's artifacts are removed).
- **SC-006**: A first-time user can locate the acceptable-use / no-harm policy from within the application in under 1 minute, and the policy explicitly states it applies to bundled data, user data, and system usage. (Verifiable: the policy page is reachable in ≤2 clicks via a persistent navigation link present in the global nav and on the data-entry surface.)
- **SC-007**: A reviewer can produce a complete, human-readable provenance-and-audit report for any single dataset in under 5 minutes using only the application's recorded data. (Verifiable: a single per-dataset governance view/endpoint returns that dataset's provenance plus its complete, chronologically-ordered audit history in one response.)
- **SC-008**: 100% of rejected submissions receive a clear, respectful explanation that states the specific reason for rejection.
- **SC-009**: Any alteration, insertion, or removal of an audit entry is detectable: an integrity check over the audit trail returns "valid" for an untouched trail and "invalid" (identifying the break point) for any tampered trail, in 100% of test cases.

## Assumptions

- **Sample data corpus**: The application already ships a fixed set of bundled sample data (literary public-domain texts, generated/hand-crafted text, and permissively-licensed name lists) seeded on first run. This feature governs that existing set rather than introducing new categories of sample data.
- **Source-of-truth for bundled provenance**: A maintained, authoritative manifest of bundled sample provenance (source, license, attribution per item) already exists in documentation form and will serve as the basis for the machine-readable provenance records.
- **Single-tenant / local deployment**: The application runs as a local/self-hosted workbench. "Actor" in audit entries refers to the operating user or session and automated processes, not a multi-tenant identity system; full multi-user identity/authentication is out of scope for this feature.
- **Content scanning depth**: The acceptable-use gate relies primarily on user declaration/affirmation plus rejection of clearly disallowed declarations and unparseable/empty content. Deep automated content classification (e.g., ML-based toxicity/PII detection) is treated as a possible later enhancement, not a requirement of this feature.
- **No-harm = ethical/legal/respectful use**: The "universal no-harm stance" is interpreted as: data is lawfully sourced and licensed, ethically and respectfully represented, used in ways that do not facilitate harm, and all of the above are auditable. The precise enumerated list of prohibited uses will be finalized in the policy document.
- **License approval governance**: The set of approved licenses is curated by project maintainers; the request to "do so legally" is satisfied by restricting acceptance to that curated, redistribution-safe set.
- **Existing protections retained**: Current safeguards (e.g., protection of bundled sample data from casual deletion) are preserved and extended, not replaced.
- **Reproducibility & layering**: Governance additions conform to the project's existing architectural and quality conventions (layered access, deterministic behavior, full test coverage) so the feature does not weaken existing guarantees.
