---
title: TYPE_CHECKING Conditional Allow with Exception Discipline
type: decision
tags:
  - type/decision
  - domain/governance
  - domain/tooling
created: 2026-06-19
updated: 2026-06-29
aliases:
  - ADR-027-type-checking-conditional-allow
source: agent
code-refs:
  - anvil/services/vault/check_guarded_imports.py
  - anvil/db/models/content_corpus.py
  - anvil/db/models/corpus.py
---

# ADR-027: TYPE_CHECKING Conditional Allow with Exception Discipline

**Status**: Reviewed  
**Created**: 2026-06-19  
**Updated**: 2026-06-29  
**Supersedes**: Constitution Additional Constraints (`TYPE_CHECKING` ban)

## Context

The constitution stated: *"`TYPE_CHECKING` from `typing` is forbidden — circular imports are an architecture problem."* Yet:

- The agent instructions (`AGENTS.md` Principle 10) *mandated* `TYPE_CHECKING` usage with PEP 563.
- Five ORM model files used `if TYPE_CHECKING:`: `content_corpus.py`, `content_version.py`, `content_entry.py`, `corpus.py`, and `corpus_file.py`.

This contradiction was the most critical governance inconsistency: an agent reading the constitution would try to *remove* the pattern, while an agent reading the agent guide would *add* it.

## Investigation

The usages were examined (see `013-dx-harness-hardening` reveal report, and 2026-06-29 ORM model merge session):

- **ORM model layer (5 files)**: Genuine bidirectional `relationship()` cycles between `ContentCorpus ↔ ContentVersion ↔ ContentEntry` (triangular) and `Corpus ↔ CorpusFile` (bidirectional FK). Initially retained as permitted exceptions.
- **`anvil/services/inference/inference.py`**: No runtime cycle. Replaced with a normal top-level import (2026-06-19).

## Decision

Replace the blanket ban with a **conditional-allow rule with a 4-point exception discipline**:

> `TYPE_CHECKING`-guarded imports are permitted ONLY to break a genuine runtime circular import that cannot be resolved without violating another constitutional rule. Each permitted use MUST satisfy:
>
> 1. The module declares `from __future__ import annotations` (the guard is type-only).
> 2. A genuine runtime circular import exists that every rule-compliant alternative would either crash or violate another rule.
> 3. The guarded symbol is referenced **only in annotations** — never in runtime code (machine-checkable by `anvil/services/vault/check_guarded_imports.py`).
> 4. A one-line comment names the specific cycle being broken.

## 2026-06-29 amendment: ORM cycle resolution via file merging

The ORM model cycles that were previously retained as permitted exceptions are now **resolved** by **co-locating the mutually-dependent classes in a single file**:

| Previous files | Merged into | Classes |
|---|---|---|
| `content_corpus.py`, `content_version.py`, `content_entry.py` | `content_corpus.py` | `ContentCorpus`, `ContentVersion`, `ContentEntry` |
| `corpus.py`, `corpus_file.py` | `corpus.py` | `Corpus`, `CorpusFile` |

This approach was previously rejected (see "Alternatives considered" below) because it violated the strict one-class-per-file rule (ADR-020). The rule was relaxed to permit multi-class model files when necessary to break circular import cycles — see AGENTS.md Principle 10 for the specific carve-out.

**Result**: Zero `if TYPE_CHECKING:` blocks remain in the model layer. The `check_guarded_imports.py` enforcer is retained to validate the remaining 15+ non-model `TYPE_CHECKING` usages in the codebase (service layer, optional deps, client SDK).

## Rationale

- The ORM cycle was structurally unavoidable given the interaction of no-string-refs, one-class-per-file, and `mypy --strict`.
- Co-location proved to be the simpler, more maintainable solution: it eliminates the import machinery entirely while preserving type safety via PEP 563.
- The discipline's machine-checkable condition (3) prevents the anti-pattern from recurring in non-model code.
- The inline-comment condition (4) makes each exception auditable at review without a central registry.

## Alternatives considered

- **Co-location of ORM classes** (initially rejected, then adopted 2026-06-29): previously rejected due to one-class-per-file (ADR-020). Re-evaluated and adopted with a specific carve-out in AGENTS.md Principle 10 for bidirectional ORM relationship cycles. The Simplicity First principle (ADR-041) justified the exception: eliminating the TYPE_CHECKING machinery is simpler than maintaining it.
- **Blanket allow** (rejected): would re-permit the `inference.py` anti-pattern — unenforceable drift.
- **Blanket ban** (rejected): would force ORM models into one-class-per-file violation or string-ref violation.

## Status

Reviewed. Amends Constitution Additional Constraints and ADR-020 (one-class-per-file). Implemented by `anvil/services/vault/check_guarded_imports.py`.

## See Also

- [[Decisions/README|Decisions]]
- [[Sessions/2026-06-29-orm-model-type-checking-elimination|2026-06-29 Session Log]]
