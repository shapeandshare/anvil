---
title: 'ADR-038: UX Rules Integration'
type: decision
tags:
  - type/decision
  - domain/governance
  - domain/ui
  - domain/tooling
created: '2026-06-21'
updated: '2026-06-21'
source: agent
code-refs:
  - docs/ux-rules.md
  - shared/ux.mk
  - scripts/ci/ux_lint.py
  - scripts/ci/ux_review.py
  - .opencode/skills/ux-review/SKILL.md
  - .opencode/skills/ux-generate/SKILL.md
  - .specify/memory/constitution.md
  - .specify/templates/checklist-template.md
  - .specify/templates/tasks-template.md
  - docs/usability/HANDOFF.md
  - docs/usability/INTEGRATION.md
aliases: 'ADR-038: UX Rules Integration'
---
# ADR-038: UX Rules Integration

## Status

Accepted

## Context

The project had no systematic UX compliance mechanism. Frontend code (Jinja templates, CSS, HTML) was written without a consistent governance model for accessibility, focus management, security (template escaping), streaming semantics, or visual design constraints. This created risk of:

- Keyboard-inaccessible UI patterns (`<div>` click handlers, no focus indicators)
- XSS holes via unaudited `|safe` filters
- Broken streaming/SSE accessibility (per-chunk `aria-live` flooding)
- Missed CSRF tokens on state-changing forms
- No deterministic gate to catch regressions

A UX ruleset was designed (`docs/ux-rules.md`) with a severity×enforceability model (S4–S1 × lint/ai-review/test), two checkers (deterministic `ux_lint.py`, AI `ux_review.py`), and two OpenCode skills (`ux-review`, `ux-generate`). The artifacts were placed in a prior commit (`7c603b3`), but open questions remained and verification was incomplete.

This ADR records the resolution of the remaining decisions and integration work.

## Decision

### Architecture

1. **Single source of truth**: `docs/ux-rules.md` is the canonical ruleset. Both skills, the linter script, and the AI review script reference it. The linter carries its own regex checks but the ruleset is the human/AI reference.
2. **Two-tier checking**:
   - **Deterministic gate** (`make ux-lint`, via `scripts/ci/ux_lint.py`): zero-dep, regex-based, catches the mechanical S4 subset (unaudited `|safe`, `outline:none`, `<div>` click handlers, `user-scalable=no`, per-chunk `aria-live="assertive"`)
   - **AI deep pass** (`make ux-review`, via `scripts/ci/ux_review.py`): optional, full ruleset, needs `UX_API_KEY`, routes through whichever model the invoker provides
3. **Injection quarantine**: Files under review are untrusted data. Embedded directives telling the reviewer to skip rules are surfaced as `[S4] security` findings — never obeyed. This is enforced in the operating contract at the top of `docs/ux-rules.md`.
4. **Two OpenCode skills**:
   - `ux-review` — audit UI/template/CSS code against the ruleset, emit file:line findings with severity
   - `ux-generate` — generate compliant code, treating S4/S3 as hard constraints

### Integration

5. **Makefile**: Targets `ux-lint` and `ux-review` live in `shared/ux.mk`, included by the root `Makefile`. The `PYTHON` variable (resolving to `.venv/bin/python3`) is used — bare `python` was a bug and has been fixed.
6. **Spec Kit governance**: A MUST principle referencing `docs/ux-rules.md` exists in `.specify/memory/constitution.md`. Additionally:
   - 14-item UX compliance checklist added to `.specify/templates/checklist-template.md`
   - `make ux-lint` verification + `make ux-review` tasks added to `.specify/templates/tasks-template.md`
7. **Generation enforcement**: Skill-only (on-demand). No `opencode.json` instructions — leaner context, agents opt in via the `skill` tool.
8. **CI**: `ux-lint` is local-only for now. Not wired into `.github/workflows/ci.yml`.

### Identifiers & naming

9. **Generic identifiers kept**: `UX_*` env vars, `ux-lint:allow` suppression, `[S<n>]` severity tags, skill names `ux-review`/`ux-generate`. Not namespaced to Anvil.
10. **Scripts rebound**: To `scripts/ci/` (repo convention for CI tools), not `ci/` as originally specified.

### Unchanged / Deferred

11. **SSE per-chunk gate gap**: Accepted. The `aria-live="polite"` per-chunk rule is AI-review-only — no runtime/Playwright gate investment.
12. **Review model**: Unopinionated — whichever agent invokes the skill provides the model.
13. **Fleet verification**: Deferred to a running OMO session where `ux-review`/`ux-generate` can be invoked via the `skill` tool at project priority.

## Consequences

### Easier

- UI regressions in the mechanical S4 set are caught locally before commit
- Agents generating UI code have explicit constraints via `ux-generate`
- Spec Kit governance surfaces UX compliance as a CRITICAL gate in `/speckit.analyze`
- Checklist and tasks templates auto-inject UX verification for UI features
- Baseline scanned: 17 pre-existing S4 violations across 35 templates — provides a measurable starting point

### Harder

- Without CI wiring, enforcement is only as strong as developer diligence in running `make ux-lint`
- AI review requires `UX_API_KEY` — friction for ad-hoc use
- SSE per-chunk violations are invisible to the deterministic gate (AI-review-only)
- The 17 pre-existing S4 violations need remediation — they're not new but the gate now surfaces them

## Compliance

- **Makefile targets**: `make ux-lint` and `make ux-review` resolve from `shared/ux.mk`
- **Constitution**: `.specify/memory/constitution.md` contains the UI compliance MUST principle
- **Smoke test**: `make ux-lint` on a file with `|safe` → `GATE: FAIL`; clean file → `GATE: PASS`
- **Skills**: On-disk at `.opencode/skills/ux-*/SKILL.md` with valid YAML frontmatter
- **Checklist**: UX compliance section present in `.specify/templates/checklist-template.md`
- **Tasks**: `make ux-lint`/`make ux-review` tasks present in `.specify/templates/tasks-template.md`
