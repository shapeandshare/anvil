---
title: Spec 049 — Learning Architecture Differences
type: session-log
tags:
  - type/session-log
  - domain/content
  - domain/ui
created: '2026-06-28'
updated: '2026-06-28'
status: draft
code-refs:
source: agent
aliases: Spec 049 Learning Architecture Differences
---

# Spec 049 — Learning Architecture Differences

**Session**: Completed the full Spec Kit lifecycle for spec 049: specification,
clarification, plan, tasks, cross-artifact analysis, and implementation of the
architecture-differences learning module — a single-page accordion lesson in
anvil's learning arc explaining how model architectures differ (tokenization,
attention, parameter scaling, context length) and what those differences mean
for fine-tuning.

## What was done

### Speckit lifecycle

1. **`/speckit.feature`** — Updated `.specify/feature.json` to point at spec
   049; created feature branch `049-learning-architecture-differences`.

2. **`/speckit.specify`** — The spec was pre-existing (draft). Ran
   `/speckit.clarify` to resolve 2 ambiguities: (a) page format → accordion
   pattern; (b) cross-link target from 041 → `#allow-list` anchor.

3. **`/speckit.plan`** — Generated `plan.md`, `research.md`, `data-model.md`,
   `quickstart.md`. Key design decisions:
   - Accordion template reusing existing FAQ `.faq-item` CSS/JS (not the
     carousel `concept.html`)
   - Single learning module with 5 accordion sections
   - `#allow-list` anchor for 041 cross-links
   - Insertion after `finetune-vs-prompt-vs-rag` in `LEARNING_ARC`

4. **`/speckit.tasks`** — Generated `tasks.md` with 16 tasks across 4 phases.

5. **`/speckit.analyze`** — Found 6 issues:
   - **HIGH (E1)**: Missing task for 041 cross-link emission side (added T016)
   - **MEDIUM (B1)**: Content prose ambiguity (accepted as authorial)
   - **LOW (F3)**: T009 missing [P] marker (fixed)
   - **HIGH during review pass**: 7 additional fixes:
     - Factual error: "32 tokens" → actual default is `block_size=16`
     - Misattributed FT-AD-10 "(allow-list aspect)" qualifier (belongs to FT-AD-11)
     - False sole-ownership claims (FR-026, FR-032, FT-AD-9/10 are shared with sibling specs)
     - FR-025a missing from Scope table
     - FR-026 was untestable prose
     - SC-002 hidden cross-spec dependency on 041 noted
     - Companion `.md` overview file synced

6. **`/speckit.implement`** — Implemented all 16 tasks:
   - `ARCHITECTURE_DIFFERENCES_STEPS` (5 sections) in `learning.py`
   - `LEARNING_ARC` entry for `architecture-differences`
   - Route handler at `/v1/learn/architecture-differences`
   - Accordion template at `archetypes/architecture-differences.html`
   - e2e test for the new route
   - Cross-link banner on `models.html` (041 emission side, T016)

### Technical notes

- The 041 HuggingFace Model Browser UI doesn't exist yet (API endpoints exist
  but no template renders them). The cross-link emission was implemented as a
  banner CTA on the existing `models.html` page, which is the closest
  equivalent for users browsing models.
- The pre-existing `test_learn_cloud_compute` failure is unrelated (string
  mismatch in title assertion) — does not affect NMRG for this feature.

## Files modified

- `.specify/feature.json` — Updated from 043 to 049
- `docs/vault/Specs/049 Learning Architecture Differences/049 Learning Architecture Differences - spec.md` — Spec with clarifications + FR ownership corrections + accuracy gate
- `docs/vault/Specs/049 Learning Architecture Differences/049 Learning Architecture Differences.md` — MOC synced
- `docs/vault/Specs/049 Learning Architecture Differences/plan.md` — Implementation plan (NEW)
- `docs/vault/Specs/049 Learning Architecture Differences/research.md` — Research decisions (NEW)
- `docs/vault/Specs/049 Learning Architecture Differences/data-model.md` — Data model (NEW)
- `docs/vault/Specs/049 Learning Architecture Differences/quickstart.md` — Implementation quickstart (NEW)
- `docs/vault/Specs/049 Learning Architecture Differences/tasks.md` — Task list (NEW)
- `AGENTS.md` — Updated via `update-agent-context.sh`
- `anvil/api/v1/learning.py` — Step data, arc entry, route handler
- `anvil/api/templates/archetypes/architecture-differences.html` — Accordion template (NEW)
- `anvil/api/templates/archetypes/models.html` — Cross-link banner CTA
- `tests/e2e/api/test_pages.py` — e2e route test

## Discoveries

- [[Discoveries/spec-041-browser-ui-not-implemented|Spec 041 HuggingFace Model Browser UI not yet implemented]] — the API endpoints exist but the browser UI template has not been built. The cross-link emission for FR-025a/SC-002 was placed on `models.html` as the closest equivalent.
- [[Discoveries/block-size-default-16-not-32|Default block_size is 16, not 32]] — the engine default is `block_size=16` not 32 as initially drafted. Verified in `anvil/core/engine.py:114`.
- [[Discoveries/faq-accordion-passes-ux-lint-with-suppression|FAQ accordion pattern passes ux-lint with suppression annotations]] — the `faq-item` pattern uses `<div onclick>` which triggers S4, but keyboard support via `faq-common.html` allows annotation with `ux-lint:allow-next`.