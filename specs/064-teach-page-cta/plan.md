# Implementation Plan: Teach Page Onboarding & CTA Remediation

**Branch**: `062-teach-page-cta` | **Date**: 2026-07-03 | **Spec**: `specs/064-teach-page-cta/spec.md`
**Input**: Feature specification from `specs/064-teach-page-cta/spec.md`

## Summary

The teaching loop page (`teach.html`) has no call to action on initial load — all panels are `display:none`, leaving a blank main content area. This plan adds: (1) an empty-state guidance card when no session is active, (2) flow continuity CTAs (post-training "Inspect This Round →"), (3) progressive disclosure of the Compare panel, (4) educational cross-references and visual polish (staggered animations, "Did You Know?" banner). All changes are frontend-only: modifications to the existing Jinja2 template, inline CSS/JS, and reference patterns from other pages.

## Technical Context

**Language/Version**: Jinja2 template + vanilla JS (ES5-compatible) + CSS3  
**Primary Dependencies**: None new — reuses existing `tokens.css`, `archetypes.css`, `base.html` `didyouknow_banner` block  
**Storage**: N/A — all state is client-side JS variables (existing pattern)  
**Testing**: Manual visual verification + Playwright browser smoke test (`make test-browser`)  
**Target Platform**: Web (FastAPI/Jinja2 serving desktop + mobile)  
**Project Type**: Web application (monolithic FastAPI + Jinja2 templates)  
**Performance Goals**: No performance impact — trivial DOM additions, no network requests  
**Constraints**: Must match existing design patterns exactly (iOS modern tokens, `--stagger-i` entrance animations, `didyouknow_banner` block); all changes must pass `make ux-lint` (deterministic S4 gate) and UX review (S3 gate)  
**Scale/Scope**: Single template file (`teach.html`) + supporting CSS/JS only — no backend changes, no new routes, no new dependencies

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

**UI compliance gate (Additional Constraints)**: All template/CSS work MUST comply with `docs/ux-rules.md`. The originating critical review identified S3 empty-state failures — these are the target of this plan.

- [x] **S4/S3 findings blocked** — the plan explicitly resolves the S3 empty-state gap (FR-001) and S3 flow continuity gap (FR-004/FR-005). No new S4/S3 findings expected.

**Simplicity First gate (Article XI — hard MUST)**: Confirm this plan favors
the simplest, most boring solution that meets the requirement:

- [x] **Simplest viable (§11.1)** — Direct template/CSS/JS modifications to existing single file. No new components, no new files, no refactoring.
- [x] **Boring over novel (§11.2)** — All patterns (staggered animation, didyouknow banner, conditional panel display) already exist in codebase; nothing new introduced.
- [x] **YAGNI (§11.3)** — Only the stated CTAs and fixes are added. No speculative session-management features, no user onboarding wizard.
- [x] **Reuse first (§11.4)** — Reuses existing `didyouknow_banner` block from `base.html`, existing `--stagger-i` pattern from `archetypes.css`, existing `section-card` and `btn` component patterns.
- [x] **Testable (§11.6)** — All changes are visually verifiable (empty state on load, CTA after training, compare panel hidden < 2 rounds). Playwright browser test can validate the full flow.

> No deviations from simplest solution — all complexity is matched to existing patterns.

## Project Structure

### Documentation (this feature)

```text
specs/064-teach-page-cta/
├── spec.md              # Feature specification
├── plan.md              # This file (implementation plan)
├── research.md          # Phase 0 — research findings (no unknowns)
├── data-model.md        # Phase 1 — workflow state machine design
├── quickstart.md        # Phase 1 — testing guide
└── contracts/           # Skipped — no external interfaces
```

### Source Code (repository root)

```text
anvil/api/templates/
├── base.html                           # [REFERENCE] didyouknow_banner block pattern
├── teach.html                          # [MODIFY] Primary target — all UX changes
└── archetypes/playground.html          # [REFERENCE] Banner CTA pattern, stagger-i usage

anvil/api/static/css/
├── tokens.css                          # [REFERENCE] Design tokens
├── archetypes.css                      # [REFERENCE] Button/Card/Form component styles
└── components.css                      # [REFERENCE] Component patterns

tests/
└── e2e/
    └── [playwright tests if added]     # [OPTIONAL] Browser smoke tests for teach flow
```

**Structure Decision**: Monolithic template — all changes confined to `teach.html` and its inline `<style>`/`<script>` blocks. No new files required. Pattern references from `playground.html`, `learn-index.html`, `base.html`.

## Complexity Tracking

> No violations to justify — all solutions are the simplest viable approach following existing patterns.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| — | — | — |