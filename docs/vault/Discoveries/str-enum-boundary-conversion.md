---
title: StrEnum Boundary Conversion Pattern
type: discovery
tags:
  - type/discovery
  - domain/architecture
created: '2026-06-19'
updated: '2026-06-19'
status: draft
aliases:
  - StrEnum Boundary Conversion Pattern
  - str-enum-boundary
source: agent
code-refs:
  - 'anvil/services/datasets/corpus_loader.py:_make_chunker'
  - 'anvil/services/datasets/corpora.py:create'
---
## StrEnum Boundary Conversion Pattern

When DB columns store strings but service code uses `StrEnum`, a friction boundary emerges because SQLAlchemy mapped columns remain typed as `Mapped[str]` (SQLite doesn't support Python enum types natively).

### The problem

```python
class Corpus(Base):
    chunking_strategy: Mapped[str] = mapped_column(String(20), default="windowed")

# Service code now expects a ChunkingStrategy enum
def _make_chunker(strategy: ChunkingStrategy) -> Chunker: ...
```

Calling `_make_chunker(corpus.chunking_strategy)` fails type-checking because `corpus.chunking_strategy` is `str`, not `ChunkingStrategy`.

### The solution

Accept both at the boundary, then convert:

```python
def _make_chunker(
    self,
    strategy: ChunkingStrategy | str,
    overlap: float,
    block_size: int | None = None,
) -> Chunker:
    if isinstance(strategy, str):
        strategy = ChunkingStrategy(strategy)
    # strategy is now strictly ChunkingStrategy
    ...
```

### Principles

1. **Boundary methods are tolerant** — accept `str | MyEnum` where DB or API strings arrive
2. **Internal methods are strict** — once converted, only accept the enum type
3. **Convert early** — convert at the outermost service boundary, never pass strings into deep logic
4. **No DB column type change** — SQLAlchemy `Mapped[str]` stays as-is; SQLite has no native enum support

### Test implications

When `StrEnum("invalid")` raises `ValueError`, the error message format is `"'invalid' is not a valid MyEnum"` — note capital letter, no underscores. Regex patterns in `pytest.raises(match=...)` must match this format. Use `(?i)` for case-insensitive matching if the old convention used snake_case class references.

### Applies to

- All DB → service boundaries where string columns feed into enum-typed parameters
- API route handlers that receive string values from JSON requests
- Config file parsers where raw strings need conversion to enum members
