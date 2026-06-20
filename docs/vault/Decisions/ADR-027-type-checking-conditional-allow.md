---
title: TYPE_CHECKING Conditional Allow with Exception Discipline
type: decision
tags:
  - type/decision
  - domain/governance
  - domain/tooling
created: 2026-06-19
updated: 2026-06-19
aliases:
  - ADR-027-type-checking-conditional-allow
source: agent
code-refs:
  - scripts/ci/check_guarded_imports.py
  - anvil/db/models/corpus.py
  - anvil/services/inference/inference.py
  - .github/workflows/ci.yml
---

# ADR-027: TYPE_CHECKING Conditional Allow with Exception Discipline

**Status**: Draft  
**Created**: 2026-06-19  
**Supersedes**: Constitution Additional Constraints (`TYPE_CHECKING` ban)

## Context

The constitution stated: *"`TYPE_CHECKING` from `typing` is forbidden — circular imports are an architecture problem."* Yet:

- The agent instructions (`AGENTS.md` Principle 10) *mandated* `TYPE_CHECKING` usage with PEP 563.
- Three source files used `if TYPE_CHECKING:`: two ORM models (`corpus.py`, `corpus_file.py`) and one service module (`inference.py`).

This contradiction was the most critical governance inconsistency: an agent reading the constitution would try to *remove* the pattern, while an agent reading the agent guide would *add* it.

## Investigation

The three usages were examined (see `013-dx-harness-hardening` reveal report):

- **`corpus.py` and `corpus_file.py`**: Genuine bidirectional `Corpus ↔ CorpusFile` ORM relationship cycle. No rule-compliant alternative exists: string-literal forward refs are banned (Principle 10), co-location violates one-class-per-file (ADR-020), and extracting a shared type doesn't help with entity↔entity circular FK references.
- **`inference.py`**: No runtime cycle. `core.autograd` is already a runtime dependency via `core.engine`. The `TYPE_CHECKING` guard was unnecessary and the redundant local import should be removed.

## Decision

Replace the blanket ban with a **conditional-allow rule with a 4-point exception discipline**:

> `TYPE_CHECKING`-guarded imports are permitted ONLY to break a genuine runtime circular import that cannot be resolved without violating another constitutional rule. Each permitted use MUST satisfy:
>
> 1. The module declares `from __future__ import annotations` (the guard is type-only).
> 2. A genuine runtime circular import exists that every rule-compliant alternative would either crash or violate another rule.
> 3. The guarded symbol is referenced **only in annotations** — never in runtime code (machine-checkable by `scripts/ci/check_guarded_imports.py`).
> 4. A one-line comment names the specific cycle being broken.

**Kept (permitted exceptions):** `anvil/db/models/corpus.py`, `anvil/db/models/corpus_file.py`.  
**Refactored (not an exception):** `anvil/services/inference/inference.py` — replaced with a normal top-level import.

## Rationale

- The ORM cycle is structurally unavoidable given the interaction of no-string-refs, one-class-per-file, and `mypy --strict`.
- The discipline's machine-checkable condition (3) prevents the anti-pattern from recurring.
- The inline-comment condition (4) makes each exception auditable at review without a central registry.

## Alternatives considered

- **Co-location of ORM classes** (rejected): violates one-class-per-file (ADR-020). Sets erosion precedent for a strongly-held rule.
- **Blanket allow** (rejected): would re-permit the `inference.py` anti-pattern — unenforceable drift.
- **Blanket ban** (rejected): would force ORM models into one-class-per-file violation or string-ref violation.

## Status

Amends Constitution Additional Constraints. Implemented by `scripts/ci/check_guarded_imports.py`, enforced by `.github/workflows/ci.yml`.