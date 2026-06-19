---
title: 'Session: __init__.py Ownership Policy'
type: session-log
tags:
  - type/session-log
  - domain/architecture
  - domain/governance
created: '2026-06-19'
updated: '2026-06-19'
aliases:
  - 'Session: __init__.py Ownership Policy'
  - init-py-ownership-policy
source: agent
status: draft
---
# Session: `__init__.py` Ownership Policy

**Date**: 2026-06-19
**Trigger**: User requested reversal of the "No `__init__.py` (Strict)" policy —
  authoritative namespace levels should have bare `__init__.py` to assert
  ownership.

## What was done

### 1. Created 11 bare `__init__.py` files

All authoritative sub-package levels under `anvil/` received docstring-only
`__init__.py` files. The specific list:

| File | Docstring |
|------|-----------|
| `anvil/core/__init__.py` | Stdlib-only training engine |
| `anvil/db/__init__.py` | Async SQLAlchemy database layer |
| `anvil/db/models/__init__.py` | ORM model definitions |
| `anvil/db/repositories/__init__.py` | Repository data-access classes |
| `anvil/services/__init__.py` | Business logic and orchestration |
| `anvil/services/chunking/__init__.py` | Text chunking strategies |
| `anvil/services/compute/__init__.py` | Compute backend abstraction |
| `anvil/api/__init__.py` | FastAPI web server and presentation |
| `anvil/api/v1/__init__.py` | API v1 route definitions |
| `anvil/storage/__init__.py` | File storage abstraction |
| `anvil/supervisor/__init__.py` | Background process manager |

Zero re-exports, zero imports — docstring-only.

### 2. Verified data-only directories have no `__init__.py`

Confirmed: `data/`, `static/`, `templates/`, `_resources/`, `_resources/migrations/`
all remain `__init__.py`-free.

### 3. Updated AGENTS.md rule #6

Replaced "No `__init__.py` (Strict)" with **`__init__.py` Ownership Policy** —
full rule text with the authoritative-levels / data-only-directories distinction.

### 4. Updated Constitution Article VI

Constitution version bumped from 1.4.0 to **1.5.0** with the same policy rewrite.

### 5. Created ADR-021

Documented the decision rationale: namespace collision risk, tooling friction,
developer confusion, and inconsistency. Filed as [[Decisions/ADR-021-init-py-ownership-policy|ADR-021]].

### 6. Updated stale references

| Document | What changed |
|----------|-------------|
| [[Sessions/2026-06-19-init-py-enforcement-audit]] | Added **SUPERSEDED** callout + post-hoc note explaining files were recreated |
| [[Sessions/2026-06-19-init-import-ban-enforcement]] | Added post-hoc note confirming import ban still valid |
| [[Decisions/010-numpy-docstring-enforcement]] | Updated stale reference to old `__init__.py` prohibition |
| `docs/user-requirements.md` | Updated `__init__.py` policy statements |

### 7. All diagnostics pass

All 11 new `__init__.py` files pass `lsp_diagnostics` with zero errors.

## Files changed

```
Created:
  anvil/core/__init__.py
  anvil/db/__init__.py
  anvil/db/models/__init__.py
  anvil/db/repositories/__init__.py
  anvil/services/__init__.py
  anvil/services/chunking/__init__.py
  anvil/services/compute/__init__.py
  anvil/api/__init__.py
  anvil/api/v1/__init__.py
  anvil/storage/__init__.py
  anvil/supervisor/__init__.py
  docs/vault/Decisions/ADR-021-init-py-ownership-policy.md  (new)
  docs/vault/Sessions/2026-06-19-__init__-py-ownership-policy.md  (new)

Modified:
  AGENTS.md
  .specify/memory/constitution.md
  docs/vault/Sessions/2026-06-19-init-py-enforcement-audit.md
  docs/vault/Sessions/2026-06-19-init-import-ban-enforcement.md
  docs/vault/Decisions/010-numpy-docstring-enforcement.md
  docs/user-requirements.md
```

## Key insight

The prior policy was enforced with good intentions (avoid re-export wiring and
brittle `__init__.py` chains). The new policy preserves those gains — imports
still use direct module paths, no re-exports exist — while adding the ownership
assertion and tooling compatibility that bare `__init__.py` files provide.

## Tags

- type/session-log
- domain/architecture
- domain/governance
- status/draft
