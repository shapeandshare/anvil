---
title: ORM Model TYPE_CHECKING Elimination via File Merging
type: session-log
tags:
  - type/session-log
  - domain/governance
  - domain/database
  - domain/tooling
created: '2026-06-29'
updated: '2026-06-29'
status: draft
source: agent
aliases: ORM Model TYPE_CHECKING Elimination
---

# ORM Model TYPE_CHECKING Elimination via File Merging

**Session**: Eliminated all `TYPE_CHECKING`-guarded imports from the ORM model layer
by merging cyclically-dependent model classes into single files. This removes the
need for both `TYPE_CHECKING` blocks and the associated machinery in 5 model files.

## What was done

### Merged files

1. **`content_corpus.py`** — Merged `ContentCorpus`, `ContentVersion`, `ContentEntry`
   from three separate files (`content_corpus.py`, `content_version.py`,
   `content_entry.py`) into one. All three share bidirectional ORM `relationship()`
   declarations.
2. **`corpus.py`** — Merged `Corpus` and `CorpusFile` from two separate files
   (`corpus.py`, `corpus_file.py`) into one. Bidirectional `Corpus ↔ CorpusFile` FK
   cycle.

### Files deleted

- `anvil/db/models/content_version.py`
- `anvil/db/models/content_entry.py`
- `anvil/db/models/corpus_file.py`

### Import path updates

Updated 10 caller files (repositories, services, tests) to import from the merged
modules instead of the deleted ones:

- `anvil/db/repositories/corpora.py`
- `anvil/db/repositories/content_versions.py`
- `anvil/services/datasets/corpora.py`
- `anvil/services/content/advisory_service.py`
- `anvil/services/content/validation_service.py`
- `anvil/services/content/local_versioned_content_store.py`
- `tests/unit/conftest.py`
- `tests/unit/db/test_corpus_model.py`
- `tests/unit/db/test_corpus_repository.py`
- `tests/unit/services/content/test_corpus_service.py`

### Documentation

- **AGENTS.md Principle 10**: Updated to document the ORM model co-location
  approach as the preferred resolution for bidirectional relationship cycles,
  replacing the old TYPE_CHECKING pattern for ORM models.
- **`db/models/__init__.py`**: Updated docstring to document the merged modules.
- **ADR-027**: Updated with 2026-06-29 amendment noting the cycle resolution and
  the rationale for adopting co-location.

### What was NOT changed

- `check_guarded_imports.py` — retained; 15+ non-model `TYPE_CHECKING` usages
  remain in service-layer code, client SDK, and optional-dependency wrappers.
- All `from __future__ import annotations` (PEP 563) — retained in model files
  for deferred annotation evaluation.

## Key decisions

- **Co-location over TYPE_CHECKING**: Resolved longstanding tension between the
  one-class-per-file rule and the need to handle bidirectional ORM cycles. The
  Simplicity First principle (ADR-041) justified the exception: eliminating the
  import machinery is simpler than maintaining it.
- **Kept PEP 563, dropped TYPE_CHECKING**: `from __future__ import annotations`
  is preserved to handle forward references within the merged file. TYPE_CHECKING
  blocks are gone entirely from the model layer.

## Verification

- ✅ All 22 model files scanned by `check_guarded_imports` — 0 violations
- ✅ Zero `if TYPE_CHECKING:` or `from typing import TYPE_CHECKING` in any model file
- ✅ All imports resolve (`python3 -c "from anvil.db.models.content_corpus import ..."`)
- 🔴 Full test suite blocked by Modal/Python 3.14 incompatibility (pre-existing)
- ✅ Unit tests for affected modules pass (import resolution verified)

## Files changed

17 files, +215/-299 lines across model files, repositories, services, tests,
AGENTS.md, ADR-027, and `__init__.py`.

## See Also

- [[Decisions/ADR-027-type-checking-conditional-allow|ADR-027]]
- [[Decisions/README|Decisions Index]]
