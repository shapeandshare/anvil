# Feature Specification: Developer & Agent Experience Hardening

**Feature Branch**: `014-dx-harness-hardening`
**Created**: 2026-06-19
**Status**: Draft
**Input**: User description: "address dx, summary from docs/agentic-harness-recommendations.md"

## Overview

anvil is an agent-first codebase: AI coding agents are primary contributors alongside humans. A review (`docs/agentic-harness-recommendations.md`) found that the project's *declared* discipline (a versioned constitution, an agent guide, strict lint/type/coverage standards, a knowledge vault) is excellent, but a **gap exists between what the project declares and what it actually enforces**. Rules are stated but not machine-checked; governance documents contradict each other and the code; and human onboarding material is thin.

For an agent-first project this gap is uniquely damaging: agents treat governance documents as literal ground truth, so a contradictory or unenforced rule produces confidently-wrong work. This feature closes that loop so that **every declared rule is either enforced and true, or amended to reflect reality**, and so that a new contributor (human or agent) can become productive quickly and trust the rules they read.

## Clarifications

### Session 2026-06-19

- Q: Coverage policy — what threshold should the enforced gate use? → A: Set the enforced threshold to the current measured coverage and ratchet it upward over time; amend the constitution's "100%" to a phased/aspirational goal via a decision record (the gate must be true-today and continuously improving, never impossible).
- Q: Are the structural refactors (god-class consolidation, `router.py` split) in scope? → A: In scope. Both are included in this feature, but each refactor MUST be delivered as its own behavior-free structural change (per Constitution §10.9), separate from the governance/CI/docs changes.
- Q: How do the new required gates interact with the existing automated bump/release PRs? → A: Automated version-bump PRs that change only the version field and changelog (no source diff) are exempt from the heavy gate suite, but a fast guard MUST verify they touch only those files; any PR with a source change — human, agent, or bot — gets the full gate suite. This keeps release automation working without creating a bypass for source changes.
- Q: How should the existing duplicate ADR numbers (008, 010, 016) be remediated? → A: Renumber the later/duplicate ADRs to the next free sequential numbers, update all inbound wikilinks in the same change, and leave a redirect/alias note at each old name. The vault-audit gate MUST pass (zero broken links) after renumbering. Going forward, a uniqueness check prevents new collisions.
- Q: How should the `TYPE_CHECKING` contradiction be resolved? → A: Conditional allow with an inline exception discipline. Permit `TYPE_CHECKING`-guarded imports ONLY to break a genuine runtime circular import that cannot be resolved without violating another constitutional rule. Keep the two ORM models (`corpus.py`, `corpus_file.py`) — their bidirectional `Corpus`↔`CorpusFile` cycle has no rule-compliant alternative. Refactor `services/inference/inference.py` to a plain top-level import of `Value` (no cycle exists; `core.autograd` is already a runtime dependency) and remove its redundant function-local re-import. Each permitted guarded import MUST satisfy four conditions: (1) the module declares `from __future__ import annotations`; (2) a genuine runtime cycle exists that every rule-compliant alternative would crash or violate (reviewer attests); (3) the guarded symbol is used ONLY in annotations, never in runtime code (grep/AST-checkable); (4) a one-line comment names the specific cycle. Co-locating both ORM classes in one file (which would avoid the guard) was considered and REJECTED because it violates one-class-per-file; this rejection is recorded so it is not relitigated. No central exception registry is added now (inline discipline suffices; revisit only if guarded imports exceed ~5). Amend the constitution + agent guide to state this rule; record via a decision record.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Trustworthy automated quality gates (Priority: P1)

A contributor (human or agent) proposes a change. Before that change can merge into the protected main line, an automated process runs the project's declared quality gates — style/lint, strict type checking, the full test suite, the coverage threshold, and the knowledge-base audit — and blocks the merge if any gate fails. The contributor sees exactly which gate failed and why.

**Why this priority**: This is the foundation. Without automated enforcement, every other declared rule (coverage, layering, conventions) is honor-system only and silently drifts. The review found that the gates the constitution says "MUST pass" are never run automatically, which is the root cause of the other findings. Making gates real makes all other rules trustworthy.

**Independent Test**: Open a change that deliberately fails one gate (e.g., a lint error, a type error, a failing test, a coverage drop). Confirm the automated check fails, names the specific failing gate, and prevents merge into the main line. Then fix it and confirm the check passes and merge is allowed.

**Acceptance Scenarios**:

1. **Given** a change proposal that introduces a style/lint violation, **When** the automated checks run, **Then** the checks fail, the failing gate is identified, and the change cannot merge into the protected main line.
2. **Given** a change proposal that introduces a type error, **When** the automated checks run, **Then** the type-check gate fails and merge is blocked.
3. **Given** a change proposal that lowers test coverage below the enforced baseline, **When** the automated checks run, **Then** the coverage gate fails and merge is blocked.
4. **Given** a change proposal where all gates pass, **When** the automated checks run, **Then** all gates report success and merge into the main line is permitted.
5. **Given** the same gates, **When** a contributor runs them locally before proposing the change, **Then** the local result matches the automated result (local/CI parity).

---

### User Story 2 - Consistent, honest governance (Priority: P2)

A contributor opens any governance document (constitution, agent guide, contributor guide) and finds a single, non-contradictory set of rules. Every rule the documents declare is one the codebase actually honors; any rule that no longer matches reality has been amended through a recorded decision rather than left to silently conflict. Coverage and other standards reflect achievable, currently-true targets.

**Why this priority**: Contradictory rules cause agents to take opposite, confident actions on the same code (the review found the constitution forbids a pattern that the agent guide mandates and the code uses). Honest standards prevent wasted effort chasing impossible bars. This depends on P1 only insofar as enforcement keeps the documents honest going forward.

**Independent Test**: Cross-read the governance documents for any rule stated in more than one place; confirm they agree. Pick each rule the review flagged as violated and confirm the code now complies or the rule was formally amended with a dated decision record. Confirm no two decision records share an identifier.

**Acceptance Scenarios**:

1. **Given** a rule that appears in more than one governance document, **When** the documents are compared, **Then** they state the same requirement (no contradictions).
2. **Given** the rule the review identified as contradictory across documents, **When** governance is reviewed, **Then** exactly one policy is stated everywhere and the codebase complies with it.
3. **Given** the declared coverage standard, **When** compared to the automatically enforced threshold, **Then** the two match and the enforced threshold is satisfiable by the current codebase.
4. **Given** the set of recorded architecture decisions, **When** their identifiers are listed, **Then** every identifier is unique.
5. **Given** any rule that was changed to reflect reality, **When** the change history is inspected, **Then** a dated, versioned decision record with rationale exists for it.

---

### User Story 3 - Fast, self-service onboarding (Priority: P3)

A newcomer (human developer or agent) starting from the project root can find, from a single starting point, an authoritative description of the architecture, the layering model, how to add a feature, which rules are mandatory, how to run the gates locally, and where past decisions are recorded — without reading source code or installing specialized tooling.

**Why this priority**: Good onboarding compounds the value of P1 and P2: once rules are trustworthy and consistent, contributors need a clear map to apply them. It is lower priority because it delivers little value if the underlying rules are still untrustworthy or contradictory.

**Independent Test**: Give the documentation set to someone unfamiliar with the project. Ask them to (a) explain the layering model, (b) state where a new service would go, (c) run all quality gates locally, and (d) find the rationale for a named past decision — using only the docs reachable from the project root.

**Acceptance Scenarios**:

1. **Given** the project root, **When** a newcomer follows the entry documentation, **Then** they can locate an architecture overview, the mandatory rules, and the commands to run gates locally without reading source code.
2. **Given** the contributor guide, **When** a newcomer reads it, **Then** it tells them where code lives, which rules are mandatory, how to run gates, and where decisions are recorded.
3. **Given** the knowledge base, **When** a newcomer without specialized tooling opens it, **Then** they find a human-readable index of architectural decisions.
4. **Given** documentation that describes the system's structure or access patterns, **When** compared to the actual code, **Then** the description matches reality.
5. **Given** the agent-facing guide, **When** it is reviewed, **Then** it contains durable rules only, with volatile per-change history kept in the changelog instead.

### User Story 4 - Consistent, navigable architecture (Priority: P4)

A contributor working on any service reaches it through one consistent access pattern, and no single file forces them to read thousands of lines of mixed concerns to make a focused change. The single service-access surface ("god class") exposes all services uniformly, and the oversized route-aggregator file is decomposed so each area of the API lives in a cohesive, appropriately-sized module.

**Why this priority**: These refactors reduce long-term onboarding friction and bring the code in line with the layering rule the constitution declares (all services through the single access surface) and the cohesion/decomposition rule already applied elsewhere. They are lowest priority because they deliver less immediate trust value than making gates real (P1) and governance honest (P2), and they depend on nothing else — they can land last without blocking the other stories.

**Independent Test**: Confirm that every service is reachable through the single access surface and that route handlers no longer live in one monolithic aggregator file; confirm each refactor landed as a behavior-free change (the test suite passes unchanged before and after, with no functional delta).

**Acceptance Scenarios**:

1. **Given** the single service-access surface, **When** a contributor inspects how each service is obtained, **Then** all services are exposed through it uniformly (no service is reached by bypassing it).
2. **Given** the API route layer, **When** a contributor opens the route-aggregation entry point, **Then** it delegates to cohesive per-area modules rather than containing the bulk of route handlers inline.
3. **Given** either structural refactor, **When** its change is reviewed, **Then** it is a standalone change containing only moves/re-wiring with zero functional behavior change, and the full test suite passes identically before and after.

---

### Edge Cases

- **Automated checks unavailable** (outage of the checking system): merges into the protected line MUST remain blocked (fail-closed), never auto-passed.
- **Intentional rule change**: when a rule must legitimately change, the amendment path (recorded decision + governance update) is the only sanctioned way to resolve a doc-vs-code conflict, rather than silently editing one side.
- **Legitimate coverage decrease** (e.g., deleting tested dead code): adjusting the enforced baseline downward requires explicit, recorded approval; it cannot happen silently.
- **Emergency/hotfix changes**: any bypass of gates MUST be explicit, attributable, and rare — not a routine path.
- **Pre-existing in-flight changes** created before gates were enforced: must be brought up to the gate standard before merging, not grandfathered silently.
- **A new decision record** colliding with an existing identifier MUST be detected and rejected before it is accepted.

## Requirements *(mandatory)*

### Functional Requirements

**Enforcement (supports User Story 1)**

- **FR-001**: The system MUST automatically validate every proposed change against all declared quality gates — style/lint, strict type checking, the full test suite, the declared coverage threshold, and the knowledge-base audit — before the change can merge into the protected main line.
- **FR-002**: Validation MUST run on every change proposal (not only after it has merged), so failures are caught before they reach the main line.
- **FR-003**: A change that fails any declared gate MUST be prevented from merging into the protected main line.
- **FR-004**: When validation fails, the contributor MUST be told which specific gate failed, with enough detail to act on it.
- **FR-005**: Contributors MUST be able to run the same gates locally and obtain results consistent with the automated checks (local/automation parity).
- **FR-006**: If the automated checking system is unavailable, merges into the protected main line MUST be blocked (fail-closed), never silently allowed.
- **FR-006a**: Automated version-bump changes that modify only the version field and changelog (no source diff) MAY be exempt from the full gate suite, but a fast guard MUST verify the change touches only those files; any change containing a source modification — regardless of author (human, agent, or bot) — MUST pass the full gate suite. The exemption MUST NOT be usable as a bypass for source changes.

**Consistency & Honesty (supports User Story 2)**

- **FR-007**: Governance documents MUST NOT contain mutually contradictory rules; any rule stated in more than one document MUST state the same requirement everywhere.
- **FR-008**: For every rule a governance document declares, the codebase MUST comply with it, OR the rule MUST be amended to reflect reality — no rule may remain that the code knowingly violates.
- **FR-009**: The coverage standard declared in governance MUST equal the coverage threshold enforced by automation, and that enforced threshold MUST be satisfiable by the current codebase.
- **FR-010**: The system MUST prevent test coverage from regressing below the established baseline; lowering the baseline MUST require explicit, recorded approval.
- **FR-011**: Every recorded architecture decision MUST have a unique identifier; the system MUST detect and reject duplicate identifiers. The existing collisions (numbers 008, 010, 016) MUST be remediated by renumbering the later duplicates to the next free numbers, updating all inbound references in the same change, and leaving a redirect/alias at each former name so no link breaks (verified by the knowledge-base audit).
- **FR-012**: Any amendment to a governance rule MUST be captured as a dated, versioned decision record that states the rationale.
- **FR-021**: The governance documents MUST state a single, consistent `TYPE_CHECKING` policy: guarded type-only imports are permitted ONLY to resolve a genuine runtime circular import that cannot be broken without violating another constitutional rule (no string-literal forward references, one-class-per-file, `mypy --strict`); everywhere else a normal top-level import MUST be used. The codebase MUST comply: the two bidirectional ORM models retain their guarded imports, and `services/inference/inference.py` MUST be changed to a normal top-level import with its redundant local re-import removed.
- **FR-022**: Each permitted `TYPE_CHECKING`-guarded import MUST satisfy an auditable exception discipline: (a) the module declares `from __future__ import annotations`; (b) a genuine runtime cycle exists with no rule-compliant alternative; (c) the guarded symbol is referenced only in annotations, never in runtime code (this condition is what disqualifies `services/inference/inference.py`); and (d) a one-line comment names the specific cycle being broken. A lightweight check MUST be able to flag a guarded symbol that is used in runtime code; a central exception registry is NOT required unless guarded occurrences exceed a documented threshold.

**Onboarding (supports User Story 3)**

- **FR-013**: The project MUST provide a single authoritative architecture document describing the system structure, the layering model, and how to add a new feature/service, understandable without reading source code.
- **FR-014**: The contributor guide MUST orient a newcomer to: where code lives, which rules are mandatory, how to run the gates locally, and where architectural decisions are recorded.
- **FR-015**: The knowledge base MUST provide a human-readable entry point (e.g., a decisions index) usable without specialized tooling.
- **FR-016**: The agent-facing guide MUST contain durable rules only; volatile per-change history MUST live in the changelog rather than the agent guide.
- **FR-017**: Documentation that describes the system's structure or access patterns MUST match the actual code; where they diverge, either the docs or the code MUST be corrected so they agree.

**Structural Architecture (supports User Story 4)**

- **FR-018**: All services MUST be reachable through the single service-access surface ("god class"); no consumer (routes, CLI, tests) may bypass it to obtain a service directly.
- **FR-019**: The API route-aggregation entry point MUST delegate to cohesive, appropriately-sized per-area modules rather than containing the majority of route handlers and business logic inline.
- **FR-020**: Each structural refactor (service-access consolidation; route decomposition) MUST be delivered as its own standalone change containing only relocation/re-wiring, with zero functional behavior change and an unchanged, passing test suite before and after.

### Key Entities

- **Quality Gate**: A declared, automatable check that a change must pass (style/lint, type check, tests, coverage threshold, knowledge-base audit). Has a pass/fail result and an actionable failure message.
- **Governance Document**: An authoritative rules document (constitution, agent guide, contributor guide). Carries versioned, non-contradictory rules.
- **Decision Record**: A dated, uniquely-identified, versioned record of an architectural or governance decision and its rationale.
- **Onboarding Guide**: Human-and-agent-facing documentation (architecture overview, contributor guide, decisions index) reachable from the project root.
- **Protected Main Line**: The default integration branch into which only gate-passing changes may merge.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of changes merged into the protected main line have passed all declared quality gates (zero gate-bypassing merges under the routine path).
- **SC-002**: Zero contradictory rules exist across governance documents (verified count of conflicts = 0).
- **SC-003**: Zero rules are knowingly violated by the codebase (verified count of known violations = 0).
- **SC-004**: The declared coverage target equals the enforced coverage threshold (gap = 0), and the enforced threshold passes on the current codebase.
- **SC-005**: 100% of architecture decision records have unique identifiers (identifier collisions = 0).
- **SC-006**: 100% of automated gate failures report the specific failing gate to the contributor.
- **SC-007**: A newcomer can locate the architecture overview, the mandatory rules, and the commands to run gates locally from a single starting document in under 10 minutes, without reading source code.
- **SC-008**: A newcomer can go from a fresh clone to a passing local gate run in under 15 minutes.
- **SC-009**: The agent-facing guide contains no per-change history entries (volatile changelog content count in the agent guide = 0).
- **SC-010**: 100% of services are reachable through the single service-access surface (services bypassing it = 0).
- **SC-011**: The route-aggregation entry point no longer holds the majority of route handlers inline, and each structural refactor landed with zero functional test-result change (behavioral delta = 0).

## Assumptions

- **Existing gate tooling is reused**: The project already provides local commands that run each gate (lint, type check, tests + coverage, knowledge-base audit). This feature wires those existing gates into automated enforcement and reconciles documentation; it does not invent new gate tooling.
- **Structural refactors are in scope, delivered separately**: The structural refactors identified in the review — consolidating the single service-access ("god class") surface and splitting the oversized route aggregator file — are **in scope** for this feature (User Story 4, FR-018–FR-020). Per the project's "structural changes get their own change" rule (Constitution §10.9), each refactor MUST land as its own behavior-free change, separate from the governance/CI/docs changes.
- **Coverage policy = ratcheting baseline**: The enforced coverage threshold is set to a currently-achievable baseline (the present measured level) and may only ratchet upward over time, rather than jumping immediately to an aspirational 100%. The aspirational target, if retained, is expressed as a phased goal recorded via decision record.
- **Contradiction resolution favors current behavior unless maintainers decide otherwise**: Where a governance rule contradicts working, intentional code (and the agent guide), the default reconciliation amends the rule to match the working behavior, recorded as a decision; maintainers may instead choose to change the code via the same recorded-decision process.
- **"Protected main line" is the default branch** of the repository.
- **Audience**: "Contributors" includes both human developers and AI coding agents; documentation and failure messages must serve both.
- **No change to runtime product behavior**: This feature targets process, enforcement, and documentation; it does not alter the trained-model or web-application behavior experienced by end users.
