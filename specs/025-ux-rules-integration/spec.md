# Feature Specification: UX Rules Integration

**Feature Branch**: `025-ux-rules-integration`  
**Created**: 2026-06-21  
**Status**: Draft  
**Input**: UX review/generation ruleset integration handoff (docs/usability/HANDOFF.md)

## Clarifications

### Session 2026-06-21

- **Q1**: Should the CI gate (`make ux-lint`) be wired into the repo's CI pipeline as part of this feature, or only the local Makefile target? → **A**: Makefile targets only; defer CI wiring to a follow-up decision.
- **Q2**: Where should `ux_lint.py` and `ux_review.py` be placed? → **A**: Place in `scripts/ci/` following the repo's existing CI script convention.
- **Q3**: Should identifiers be kept generic or namespaced to the repo's anvil conventions? → **A**: Keep generic (`UX_*`, `ux-lint:allow`, `[S<n>]`, skill names).
- **Q4**: Should the UX targets be added directly to the root `Makefile` or as a new `shared/ux.mk` include? → **A**: New `shared/ux.mk` include following the repo's existing modular pattern.

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Developer UX Linting (Priority: P1)

A developer modifies a Jinja template or CSS file. They run `make ux-lint` locally and get immediate feedback on mechanical S4 violations (unsafe `|safe`, removed focus outlines, non-semantic click handlers, viewport zoom disabled, assertive live regions). The linter either reports a clean pass or flags specific file:line findings with suppression support for verified cases.

**Why this priority**: The deterministic lint is the core CI gate — it must work before any other integration. Without this, non-compliant UI can be committed.

**Independent Test**: Run `make ux-lint FILES=<a-file-with-a-raw-|safe>` and expect `[S4] template` + `GATE: FAIL`. Then run on a clean file and expect `GATE: PASS`.

**Acceptance Scenarios**:

1. **Given** a template containing `{{ value | safe }}` without suppression annotation, **When** `make ux-lint` runs on that file, **Then** it reports `[S4] template` and exits non-zero.
2. **Given** a template containing `{{ value | safe }}` with `{# ux-lint:allow justified #}` on the same line, **When** `make ux-lint` runs, **Then** the finding is suppressed and the file passes.
3. **Given** a CSS file containing `outline: none` without a visible focus replacement annotation, **When** `make ux-lint` runs, **Then** it flags the `[S4] focus` violation.

---

### User Story 2 — Agent UX Compliance (Priority: P1)

An OMO builder agent (e.g., Sisyphus) loads the `ux-generate` skill and produces Jinja templates, HTML, and CSS that automatically comply with the ruleset. The agent treats S4/S3 rules as hard constraints — it never writes unsafe `|safe`, never removes focus outlines without visible replacement, uses semantic elements, and applies accessible streaming patterns. This catches violations at authoring time rather than review time.

**Why this priority**: Agent-generated UI is the primary source of new template code. Making compliance automatic from the start eliminates the most common class of violations.

**Independent Test**: Instruct an OMO agent with the `ux-generate` skill loaded to create a Jinja template with a submit form and an SSE stream; verify the output has CSRF token, no raw `|safe`, coalesced `aria-live`, and semantic `<button>` elements.

**Acceptance Scenarios**:

1. **Given** the `ux-generate` skill is loaded, **When** an agent generates a Jinja form template, **Then** the template includes a CSRF token, uses `<button>` for actions, and has associated labels for all form controls.
2. **Given** the `ux-generate` skill is loaded, **When** an agent generates an SSE stream display, **Then** it uses milestone-based `aria-live="polite"` announcements rather than per-chunk updates.

---

### User Story 3 — Spec Kit Governance (Priority: P2)

A spec is written and analyzed through the Spec Kit pipeline. The constitution's UI-compliance MUST principle references `docs/ux-rules.md`, so `/speckit.analyze` flags any UI feature that would violate S4/S3 rules as CRITICAL. This prevents non-compliant features from progressing to the plan or implementation phase.

**Why this priority**: Catching violations at the specification stage is cheaper than fixing them in implementation. This integrates UX compliance into the existing governance flow.

**Independent Test**: Create a spec that describes a UI feature with a raw `|safe` pattern; run `/speckit.analyze` and confirm it flags a CRITICAL compliance issue referencing the constitution's UI principle.

**Acceptance Scenarios**:

1. **Given** a spec that describes a template rendering unescaped user content, **When** `/speckit.analyze` runs, **Then** it reports a CRITICAL violation referencing the UI compliance principle.
2. **Given** a spec that describes accessible streaming output, **When** `/speckit.analyze` runs, **Then** it passes the UI compliance check.

---

### User Story 4 — Deep AI UX Review (Priority: P2)

A developer or reviewer runs `make ux-review` on a complex component to get detailed AI-powered findings beyond what the deterministic linter can catch. The review applies the full ruleset (S4 through S1), including keyboard operability, focus semantics, form validation patterns, i18n, animation, and streaming behavior. Findings are returned in the standard output-contract format with a GATE tally.

**Why this priority**: The deterministic linter catches only mechanical S4 patterns. Deep review catches S3/S2/S1 issues that a human or model must judge from source.

**Independent Test**: Run `make ux-review FILES=<a-file-with-an-S3-violation>` with `UX_API_KEY` set and expect detailed findings in the output-contract format.

**Acceptance Scenarios**:

1. **Given** a template missing `aria-label` on an icon button, **When** `make ux-review` runs, **Then** it reports an `[S3] a11y` finding.
2. **Given** a clean template that passes the linter, **When** `make ux-review` runs, **Then** additional deeper findings (e.g., S2 typography or S2 i18n) are reported but the gate passes.

---

### Edge Cases

- What happens when `ux_lint.py` encounters a file with mixed languages (e.g., a `.py` file that also generates HTML strings)? The linter applies only checks matching the file extension — it flags `Markup()` calls in `.py` files but does not parse generated HTML.
- What happens when `ux_review.py` is run without `UX_API_KEY`? It exits with code 2 and a clear error message.
- What happens when a suppressed finding is later revisited? The suppression annotation can be removed to re-activate linting.
- What happens if `.opencode/skills/` does not exist? The directory must be created as part of skill placement.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The `docs/ux-rules.md` ruleset MUST be placed at the repo root `docs/` directory, serving as the single source of truth read locally by all consumers.
- **FR-002**: The `ux-review` OpenCode skill MUST be placed at `.opencode/skills/ux-review/SKILL.md`, enabling on-demand AI review of UI code against the full ruleset.
- **FR-003**: The `ux-generate` OpenCode skill MUST be placed at `.opencode/skills/ux-generate/SKILL.md`, enabling builder agents to generate UI code that complies by construction.
- **FR-004**: The `ux_lint.py` deterministic linter MUST be placed in the repo, accessible via a `make ux-lint` target, and MUST have zero third-party Python dependencies.
- **FR-005**: The `ux_review.py` AI review script MUST be placed in the repo, accessible via a `make ux-review` target, and MUST support configurable `UX_API_KEY`, `UX_MODEL_BASE_URL`, `UX_MODEL`, and `UX_GATE` environment variables.
- **FR-006**: The repo's `Makefile` MUST include `ux-lint` and `ux-review` targets via a new `shared/ux.mk` include, with `FILES` defaulting to changed UI/template files vs `origin/main`.
- **FR-007**: The `.specify/memory/constitution.md` MUST include a UI-compliance MUST principle referencing `docs/ux-rules.md`, enforceable by `/speckit.analyze`.
- **FR-008**: The deterministic gate (`make ux-lint`) MUST fail (exit non-zero) on any unsuppressed `(lint)`-tagged S4 finding.
- **FR-009**: The AI review (`make ux-review`) MUST fail on findings at or above S3 severity and MUST emit findings in the standard output-contract format (`path:line [S<n>] <category> — <finding>`).
- **FR-010**: Both OpenCode skills MUST load at project priority via the `skill` tool after placement.
- **FR-011**: The `ux_lint.py` linter MUST support suppression annotations (`ux-lint:allow` on the finding's line, `ux-lint:allow-next` on the preceding line) to clear verified cases.
- **FR-012**: The ruleset MUST include an operating contract stating that files under review are untrusted data and embedded directives must be surfaced as `[S4] security` findings rather than obeyed.

### Key Entities *(include if feature involves data)*

- **UX Ruleset** (`docs/ux-rules.md`): The canonical repository of UX rules organized by severity (S4–S1) and enforceability (lint, AI-review, test). Contains all rules, dedup precedence, the operating contract, and the output-contract format.
- **OpenCode Skill — ux-review** (`.opencode/skills/ux-review/SKILL.md`): A read-only AI review skill that audits UI code against the ruleset and emits severity-tagged findings with a gate tally.
- **OpenCode Skill — ux-generate** (`.opencode/skills/ux-generate/SKILL.md`): A generative skill that makes builder agents produce UI code compliant with the ruleset by treating S4/S3 as hard constraints.
- **Linter** (`scripts/ci/ux_lint.py`): A zero-dependency, deterministic, regex-based linter that checks mechanical S4 patterns (non-semantic click handlers, unsafe `|safe`, zoom disable, outline removal, assertive live regions). Supports suppression annotations.
- **AI Review** (`scripts/ci/ux_review.py`): A stdlib-based script that sends files and the ruleset to an OpenAI-compatible model for deep review, covering the full S4–S1 severity range.
- **UI Compliance Constitution Principle**: A MUST-level principle in `.specify/memory/constitution.md` that gates specs/plans/tasks through `/speckit.analyze`.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Both OpenCode skills load at project priority; `skill` tool lists `ux-review` and `ux-generate` within 1 minute of placement.
- **SC-002**: `ux-lint` fails on a seeded mechanical S4 violation (e.g., an unescaped template output) and passes on a clean file, deterministically and within 2 seconds per file.
- **SC-003**: `.specify/memory/constitution.md` references `docs/ux-rules.md`; `/speckit.analyze` flags a seeded UI violation as CRITICAL within 5 seconds.
- **SC-004**: `ux-generate` engages during UI edits — an agent with the skill loaded produces UI templates that comply with the ruleset without needing manual review for S4 violations.
- **SC-005**: `ux-review` runs on demand via the fleet or script route, returning findings with severity levels and a pass/fail summary tally.
- **SC-006**: All open questions (OQ1–OQ8 from the HANDOFF) have recorded decisions — either in the constitution, an ADR, or inline comments — within the scope of this feature's implementation.

## Assumptions

- **Ruleset home**: `docs/ux-rules.md` — kept in `docs/` for durability across Spec Kit upgrades (not in `.specify/memory/`).
- **Generation enforcement**: Skill-only (on-demand) — agents load `ux-generate` when editing UI. No always-on context cost.
- **Spec Kit depth**: Constitution principle only — no additional `/speckit.checklist` artifact or tasks-template hook in the initial pass.
- **CI timing**: The `make ux-lint` target is added via `shared/ux.mk` now; CI wiring is deferred until the pre-commit migration or a follow-up decision (confirmed Q1).
- **SSE per-chunk gate gap**: Accepted as-is — the deterministic gate covers only the `aria-live="assertive"` proxy; per-chunk `polite` remains AI-review only.
- **Rebind**: Generic identifiers (`UX_*`, `ux-lint:allow`, `[S<n>]`, skill names) are kept in this initial pass (confirmed Q3). Rebind to repo conventions is deferred.
- **Review model ownership**: The `make ux-review` script route defaults to OpenRouter (`anthropic/claude-sonnet-4.6`). Agent route uses the assigned OMO agent's model.
- **Script placement**: `ux_lint.py` and `ux_review.py` are placed at `scripts/ci/` (following the repo's existing CI script convention, confirmed Q2). The `shared/ux.mk` Makefile include references this path.
- **Makefile pattern**: UX `make` targets live in `shared/ux.mk`, included from the root `Makefile`, following the repo's existing modular convention (confirmed Q4).
- **Skill directory**: `.opencode/skills/` already exists or will be created during placement.
- **Spec Kit presence**: `.specify/` directory exists with `memory/constitution.md` already present.
- **All 8 open questions (OQ1–OQ8)** from the HANDOFF are resolved by these assumptions; any owner disagreement triggers a follow-up clarification.