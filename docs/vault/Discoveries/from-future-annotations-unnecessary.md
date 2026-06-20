---
aliases:
  - Future Annotations Unnecessary
code-refs:
  - anvil/db/models/corpus.py
  - anvil/db/models/corpus_file.py
  - scripts/ci/graph_health/
  - AGENTS.md
created: '2026-06-19'
related: []
session: 2026-06-19-type-checking-and-future-annotations-removal
source: agent
status: superseded
summary: >-
  This finding was reversed by the project owner on 2026-06-19. PEP 563
  (`from __future__ import annotations`) is now the preferred approach
  over string-literal forward references. See AGENTS.md rule #9 for
  current convention.
tags:
  - type/discovery
  - domain/architecture
  - status/superseded
title: '`from __future__ import annotations` Is Unnecessary in a Python 3.11+ Codebase'
type: discovery
updated: '2026-06-19'
---
> **⚠️ SUPERSEDED**: This finding was reversed by project owner on 2026-06-19. The new convention prefers `from __future__ import annotations` (PEP 563) over string-literal forward references. See the updated `AGENTS.md` rule #10 (Forward References via PEP 563) and the session log [[Sessions/2026-06-19-type-checking-and-future-annotations-removal|TYPE_CHECKING and Future Annotations Removal]].

A Python 3.11+ codebase never needs `from __future__ import annotations` (PEP 563). A systematic audit of 49 files in the anvil codebase — many with SQLAlchemy `Mapped` forward refs, dataclass self-references, and cross-module type annotations — confirmed zero dependencies on PEP 563 deferred evaluation.

## Why It Works

**PEP 604 union syntax** (`str | None`, `int | float`) became valid Python syntax in 3.10, not just in annotations — so no import is needed to use it.

**String-literal forward references** (`-> "MyClass"`, `Mapped[list["OtherClass"]]`) work without PEP 563 because string literals in subscript expressions like `list["OtherClass"]` are just **values passed to `__class_getitem__`**, not name lookups. The expression `list.__class_getitem__("OtherClass")` returns `types.GenericAlias(list, ("OtherClass",))` without ever resolving `"OtherClass"` as a name. This means:

- `Mapped[list["CorpusFile"]]` — works at module load time even though `CorpusFile` is defined later in the same file
- `Mapped["Corpus | None"]` — `"Corpus | None"` is just a string literal passed to `Mapped.__class_getitem__`
- `def from_chars(cls, chars: list[str]) -> "Vocabulary":` — the `"Vocabulary"` return annotation is stored as-is

## When This Breaks

The pattern breaks only if you use a **bare name** forward reference without quotes AND without PEP 563:

```python
# BROKEN (NameError at module load time):
class A:
    def method(self) -> B:  # B is not defined yet
        ...

class B: ...
```

But the fix is trivial — always quote forward references:

```python
# WORKS:
class A:
    def method(self) -> "B":  # string literal, not a name lookup
        ...

class B: ...
```

## Impact

Removing `from __future__ import annotations` across 49 files eliminated:
- ~50 lines of boilerplate
- A conceptual crutch that masked the actual annotation evaluation model
- Compatibility concern with tools (like Pydantic, SQLAlchemy) that use `get_type_hints()` to resolve annotations at runtime — eager evaluation is actually more predictable

## References

- `AGENTS.md` rule #9 forbids both `TYPE_CHECKING` and `from __future__ import annotations`
- All files in `anvil/db/models/`, `anvil/services/`, `scripts/ci/graph_health/`, and tests were cleaned
- Session log: [[Sessions/2026-06-19-type-checking-and-future-annotations-removal|TYPE_CHECKING and Future Annotations Removal Session]]
