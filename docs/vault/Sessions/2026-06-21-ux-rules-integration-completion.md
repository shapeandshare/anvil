---
title: UX Rules Integration — Completion
type: session-log
tags:
  - type/session-log
  - domain/governance
  - domain/ui
  - domain/tooling
created: '2026-06-21'
updated: '2026-06-21'
status: draft
aliases: UX Rules Integration — Completion
source: agent
---
# UX Rules Integration — Completion

**Session**: Completed remaining items from the UX governance integration handoff (`docs/usability/HANDOFF.md`). See [[Decisions/ADR-038-ux-rules-integration|ADR-038]] for the full architecture decision record.

## What was done

- **OQ decisions recorded** — all 8 open questions resolved via owner decisions (see [[Decisions/ADR-038-ux-rules-integration|ADR-038]] for complete rationale)
- **T006** — Generation enforcement decided: skill-only (on-demand, no `opencode.json`)
- **T007** — Skills verified on-disk at `.opencode/skills/ux-review/SKILL.md` and `ux-generate/SKILL.md` with valid YAML frontmatter
- **T008** — Smoke-tested `make ux-lint`:
  - `concept.html` (has `|safe`) → `GATE: FAIL [S4:1]`
  - `README.md` (clean) → `GATE: PASS`
- **T011** — CI timing decided: leave local for now
- **OQ3** — Spec Kit depth: Full implementation:
  - UX compliance checklist added to `.specify/templates/checklist-template.md` (14 check items)
  - `make ux-lint` + `make ux-review` verification tasks added to `.specify/templates/tasks-template.md`
- **Bug fix**: `shared/ux.mk` was using bare `python` instead of `$(PYTHON)` — fixed

## Remaining (deferred to OMO session)

- T007 runtime verification (skill tool listing from within OpenCode)
- T009 fleet usage confirmation (agent-invoked `ux-review`/`ux-generate`)

## Key decisions

Full rationale in [[Decisions/ADR-038-ux-rules-integration|ADR-038: UX Rules Integration]].

| OQ | Decision |
|----|----------|
| OQ1 | Keep `docs/ux-rules.md` |
| OQ2 | Skill-only (on-demand) |
| OQ3 | Full: constitution + checklist template + tasks template |
| OQ4 | Leave local (no CI) |
| OQ5 | Default/unopinionated |
| OQ6 | Accept as-is |
| OQ7 | Keep generic identifiers; scripts rebounded to `scripts/ci/` |
| OQ8 | `.specify/` already present, constitution merged |

## Baseline

`make ux-lint` on all 35 template files: **17 S4 violations** (2 `|safe` on `concept.html`/`data-fundamentals.html`, 15 `<div>` click-handler on `faq.html`/`glossary.html`).
