---
title: 2026-06-22 Simplicity First Constitution Amendment
type: session-log
tags:
  - type/session-log
  - domain/governance
source: agent
created: 2026-06-22
updated: 2026-06-22
aliases:
  - 2026-06-22 Simplicity First Constitution Amendment
---

# Session: Simplicity First Constitution Amendment

## What was done

Amended the agentic governance docs to favor simple, boring, proven solutions
over untested or complex ones — a full constitutional amendment with a hard
MUST gate.

1. **Constitution** (`.specify/memory/constitution.md`): added **Article XI —
   Simplicity First (Boring Technology)** with six sub-rules (§11.1 simplest
   viable, §11.2 boring over novel, §11.3 YAGNI, §11.4 reuse before
   introducing, §11.5 justify every deviation in Complexity Tracking, §11.6
   untested paths are not done). Bumped version **1.7.0 → 1.8.0** (MINOR),
   `Last Amended` → 2026-06-22, and prepended a Sync Impact Report HTML comment.

2. **ADR** (`Decisions/ADR-041-simplicity-first-boring-technology.md`):
   documented the amendment (context, decision table, consequences,
   compliance). Added the index row to `Decisions/README.md`.

3. **Agent guidance** (`AGENTS.md`): added Behavioral Principle 13 (Simplicity
   First) with correct/incorrect examples, an Architecture Rules bullet, and
   refreshed the `Last updated` header note.

4. **Plan template** (`.specify/templates/plan-template.md`): the Constitution
   Check gate now carries an explicit Article XI simplicity checklist that
   points at the existing Complexity Tracking table as the justification record.

### Files changed

- Created: `docs/vault/Decisions/ADR-041-simplicity-first-boring-technology.md`,
  this session log
- Modified: `.specify/memory/constitution.md`, `AGENTS.md`,
  `.specify/templates/plan-template.md`, `docs/vault/Decisions/README.md`

### Sync decisions

- `spec-template.md` / `tasks-template.md`: no change — neither has a
  principle-gate section, and the Polish phase already covers cleanup/refactor.
- `docs/vault/Governance/Constitution.md`: unchanged thin redirect to the
  canonical source (intentionally not duplicated).

## Related

- [[Decisions/ADR-041-simplicity-first-boring-technology]]
- [[Governance/Constitution]]
- [[Decisions/ADR-026-coverage-ratcheting-baseline]]
