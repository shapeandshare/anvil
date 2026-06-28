---
title: Implementation Plan — Subword Tokenizer Abstraction
type: spec
tags:
  - type/spec
created: '2026-06-28'
updated: '2026-06-28'
---
# Implementation Plan: Subword Tokenizer Abstraction

**Branch**: `043-subword-tokenizer-abstraction` | **Date**: 2026-06-28 | **Spec**: [[spec.md]]
**Input**: Feature specification from `docs/vault/Specs/043 Subword Tokenizer Abstraction/spec.md`

## Summary

Tokenization is abstracted behind an anvil-owned protocol so models carry their tokenizer as a first-class artifact. Two implementations: the existing char-level `Vocabulary` (native) and a new `SubwordTokenizer` wrapping HuggingFace fast/SentencePiece tokenizers (behind `[finetune]` extra). Encode/decode dispatches on the recorded `TokenizerFamily` (`char` | `subword`). Tokenizer artifacts live alongside model files in `FileStore` — flat on export matching HF convention for `AutoTokenizer.from_pretrained()` compatibility.

## Technical Context

**Language/Version**: Python 3.11+ (PEP 604 unions, `StrEnum`, `from __future__ import annotations`)
**Primary Dependencies**: FastAPI, async SQLAlchemy + aiosqlite, Jinja2, `safetensors`, `numpy` (existing); `transformers`/`tokenizers` (new — behind `[finetune]` extra only)
**Storage**: `LocalFileStore` (model artifacts + co-located tokenizer files); SQLite (app DB for metadata)
**Testing**: `pytest` + `pytest-asyncio`; `httpx.AsyncClient` for e2e; contract tests for char-level byte parity
**Target Platform**: Linux / macOS server
**Project Type**: Python library + web service
**Performance Goals**: Zero regression on char-level encode/decode; subword tokenizer loading at model-import time (not on every inference call); INFO log on dispatch is acceptable overhead
**Constraints**:
- `anvil/core/` MUST remain zero-dependency — the abstraction protocol/ABC lives here, but `SubwordTokenizer` implementation MUST NOT be importable from base install
- Immutable tokenizer attachment — swapping means a new model artifact
- Fail fast with `TokenizerLoadError` on corrupt/missing/unsupported tokenizer files
**Scale/Scope**: Single tokenizer per model instance; tens of models max; subword tokenizer files are <100MB each (SentencePiece `.model` ~10MB, `tokenizer.json` ~50MB)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

**Article I — Zero-Dependency Core**: The abstraction protocol/ABC lives in `anvil/core/` with zero imports. The `SubwordTokenizer` implementation is behind `[finetune]` extra — guarded at import time. ✅

**Article IV — TDD Mandatory**: Contract tests prove char-level byte-for-byte parity pre- and post-abstraction. Unicode edge cases (emoji, CJK, combining diacritics, null) are explicit test cases. ✅

**Article VI — `__init__.py` Ownership**: New domain sub-packages get bare docstring-only `__init__.py`. No re-exports. ✅

**Article VII — Layered Architecture**: Tokenizer abstraction is consumed by `LoadedModel` (layer boundary: service). New tokenizer repository reads from `FileStore`. No DB leak. ✅

**Article X — Domain-Driven Package Decomposition**: Tokenizer types co-locate with the inference domain (they are tightly coupled to `LoadedModel`). Cross-family discriminator (`TokenizerFamily`) lives in `_shared`. ✅

**Article XI — Simplicity First (Boring Technology)**:
- [x] **Simplest viable** (§11.1) — a protocol with two implementations; no plugin registry, no dynamic discovery, no factory abstraction layer until a third family exists
- [x] **Boring over novel** (§11.2) — HF `tokenizers` library is the mature standard for subword; not novel
- [x] **YAGNI** (§11.3) — only two tokenizer families (char, subword); no registry, no plugin system, no configurable strategy chain
- [x] **Reuse first** (§11.4) — `Vocabulary.encode`/`decode` interface is the protocol shape; `LocalFileStore` reuses existing storage layer
- [x] **Testable** (§11.6) — contract tests, round-trip tests, unicode tests; char-level path is byte-for-byte verifiable

**Additional Constraints**:
- `mypy --strict` with zero type-error suppression ✅
- `TYPE_CHECKING` only for genuine cycles; `from __future__ import annotations` on all files ✅
- Pydantic `BaseModel` for structured data; no new `@dataclass` ✅
- One class per file ✅

> No complexity tracking needed — all decisions are the simplest viable option. See spec's Rejected Alternatives section for documented tradeoffs.

## Project Structure

### Documentation (this feature)

```text
docs/vault/Specs/043 Subword Tokenizer Abstraction/
├── spec.md              # Feature specification (source)
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
└── tasks.md             # Phase 2 output (speckit.tasks)
```

### Source Code (repository root)

```text
anvil/
├── core/
│   ├── tokenizer.py         # EXISTING — char-level Tokenizer (kept for backward compat)
│   ├── vocabulary.py        # EXISTING — char-level Vocabulary (becomes a Tokenizer impl)
│   ├── _tokenizer_base.py   # NEW — Tokenizer protocol/ABC (stdlib-only, zero deps)
│   ├── vocabulary.py        # EXISTING — updated: implements Tokenizer protocol
│   └── engine.py            # EXISTING — updated: save()/load() persist tokenizer_family + serialization_type
├── services/
│   ├── inference/
│   │   ├── inference.py     # EXISTING — updated: builds tokenizer via factory, uses protocol
│   │   ├── loaded_model.py  # EXISTING — updated: carries Tokenizer; chars/bos_id properties
│   │   ├── tokenizer_factory.py    # NEW — TokenizerFactory (dispatch linchpin)
│   │   ├── _subword_tokenizer.py   # NEW — HFFastTokenizer (+ SentencePieceTokenizer or split file)
│   │   └── demo_model_provider.py  # EXISTING — updated: provider + warmup export call
│   ├── training/
│   │   └── export.py        # EXISTING — updated: export()/retry_export() new signature
│   ├── compute/
│   │   └── modal_backend.py # EXISTING — updated: export() call site
│   └── _shared/
│       ├── tokenizer_family.py    # NEW — TokenizerFamily StrEnum (char | subword)
│       ├── serialization_type.py  # NEW — SerializationType StrEnum
│       └── tokenizer_load_error.py # NEW — TokenizerLoadError exception
├── storage/
│   └── interface.py         # EXISTING — FileStore reused for tokenizer artifacts
├── cli.py                   # EXISTING — updated: export() call site
└── api/
    └── v1/
        ├── training.py      # EXISTING — updated: export() call site
        └── experiments.py   # EXISTING — updated: retry_export() call site + tokenizer metadata

tests/
├── unit/
│   ├── core/
│   │   ├── test_tokenizer.py            # EXISTING
│   │   └── test_tokenizer_protocol.py   # NEW — char-level protocol parity + unicode tests
│   └── services/
│       ├── test_inference.py            # EXISTING — updated for new LoadedModel signature
│       ├── test_export.py               # EXISTING — updated for new export signature
│       ├── test_subword_tokenizer.py    # NEW — HF subword tests (requires finetune extra)
│       └── test_tokenizer_factory.py    # NEW — factory dispatch + error paths + NMRG-old-checkpoint
└── e2e/
    └── test_endpoints.py                # EXISTING — minor updates
```

> **Test layout**: follows the EXISTING flat convention — `tests/unit/services/test_*.py` and `tests/unit/core/test_*.py`. NOT nested under `services/inference/` (no such directory exists in the codebase).

**Structure Decision**: The tokenizer abstraction lives in `anvil/core/_tokenizer_base.py` (stdlib-only). The two discriminator enums live in separate files in `anvil/services/_shared/` (cross-domain, one-class-per-file). The subword implementation(s) and the `TokenizerFactory` (dispatch linchpin) live in `anvil/services/inference/` (tightly coupled to inference). `LlamaModel.save()/load()` gain tokenizer-metadata persistence. This is a cross-cutting refactor touching 5 export call sites + the inference/eval/learning consumers.

## Complexity Tracking

> No violations. Every approach is the simplest viable option per Article XI.
> See spec.md §Rejected Alternatives for documented tradeoffs.