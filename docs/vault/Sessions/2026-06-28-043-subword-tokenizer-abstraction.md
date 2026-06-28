---
title: 'Session: 043 Subword Tokenizer Abstraction — Implementation'
type: session-log
tags:
  - type/session-log
  - domain/core
  - domain/training
created: '2026-06-28'
updated: '2026-06-28'
aliases:
  - Session: 043 Subword Tokenizer Abstraction
status: draft
source: agent
code-refs:
  - anvil/core/_tokenizer_base.py
  - anvil/core/vocabulary.py
  - anvil/core/engine.py
  - anvil/services/_shared/tokenizer_family.py
  - anvil/services/_shared/serialization_type.py
  - anvil/services/_shared/tokenizer_load_error.py
  - anvil/services/inference/tokenizer_factory.py
  - anvil/services/inference/_subword_tokenizer.py
  - anvil/services/inference/loaded_model.py
  - anvil/services/inference/inference.py
  - anvil/services/training/export.py
  - anvil/api/app.py
  - pyproject.toml
  - tests/unit/core/test_tokenizer_protocol.py
  - tests/unit/services/test_subword_tokenizer.py
  - tests/unit/services/test_tokenizer_factory.py
  - tests/unit/services/test_inference.py
---

# Session: 043 Subword Tokenizer Abstraction — Full Implementation

**Date**: 2026-06-28
**Branch**: `043-subword-tokenizer-abstraction`
**Spec**: [[Specs/043 Subword Tokenizer Abstraction/043 Subword Tokenizer Abstraction|043 Subword Tokenizer Abstraction]]

## What was done

### Spec kit workflow (clarify → plan → tasks → analyze → implement)

Completed the full speckit pipeline for spec 043:

1. **Clarify**: Asked 7 targeted questions covering storage layout (alongside), immutability (yes), logging (INFO), rejected alternatives (char-level vs HF everywhere, forced HF interface), export format (flat alongside per HF convention), error surfaces (fail-fast with `TokenizerLoadError`), and unicode edge cases (emoji, CJK, combining diacritics, null char in contract tests).

2. **Plan**: Wrote `plan.md` with Technical Context, Constitution Check (all articles pass), Project Structure aligning with actual codebase layout. Identified the critical dispatch chain (save/load → factory → LoadedModel → inference).

3. **Tasks**: Generated 27 tasks across 4 phases. A critical re-review against the actual codebase found 8 issues the structural analysis missed — including 4 that would have produced a non-working feature (missing tokenizer persistence in LlamaModel.save/load, no factory/dispatch task, orphaned export call sites, wrong test file paths).

4. **Analyze**: Cross-artifact consistency check. Remediated all findings.

5. **Implement**: Executed all 27 tasks. 172 tests passing (0 regressions against pre-existing suite).

### Architecture

The dispatch chain:

```
LlamaModel.save() → JSON (tokenizer_family + serialization_type)
         ↓
LlamaModel.load() → reads back with char defaults for old checkpoints
         ↓
TokenizerFactory → dispatches on family → Tokenizer protocol
         ↓
LoadedModel → carries Tokenizer; chars/bos_id as properties
         ↓
InferenceService → uses protocol; all .vocab.* refs migrated
```

### Files created (7 new)

| File | Purpose |
|------|---------|
| `anvil/core/_tokenizer_base.py` | `Tokenizer` ABC protocol (stdlib-only, zero deps) |
| `anvil/services/_shared/tokenizer_family.py` | `TokenizerFamily` StrEnum (`CHAR`, `SUBWORD`) |
| `anvil/services/_shared/serialization_type.py` | `SerializationType` StrEnum (`CHAR_JSON`, `HF_FAST`, `SENTENCEPIECE`) |
| `anvil/services/_shared/tokenizer_load_error.py` | `TokenizerLoadError` exception with file_path/cause |
| `anvil/services/inference/tokenizer_factory.py` | `create_tokenizer()` — dispatch linchpin |
| `anvil/services/inference/_subword_tokenizer.py` | `HFFastTokenizer` + `SentencePieceTokenizer` wrappers |
| `tests/unit/core/test_tokenizer_protocol.py` | 13 contract tests (char-level parity + unicode) |
| `tests/unit/services/test_subword_tokenizer.py` | 4 HF tokenizer tests (skipif gated) |
| `tests/unit/services/test_tokenizer_factory.py` | 10 factory dispatch + error path tests |

### Files modified (7 changed)

| File | What changed |
|------|-------------|
| `pyproject.toml` | Added `[finetune]` extra |
| `anvil/core/vocabulary.py` | Implements `Tokenizer` protocol; `vocab_size`/`bos_id` as properties |
| `anvil/core/engine.py` | `save()`/`load()` persist `tokenizer_family` + `serialization_type` |
| `anvil/services/inference/loaded_model.py` | Accepts `Tokenizer`; `chars`/`bos_id` as properties; `info()` includes tokenizer metadata |
| `anvil/services/inference/inference.py` | Uses `TokenizerFactory`; all `loaded.vocab.*` → `loaded.tokenizer.*`/`loaded.bos_id`; `_is_bos`/`_token_label` helpers; INFO logging |
| `anvil/services/training/export.py` | `export()`/`retry_export()` write tokenizer metadata to `config.json` |
| `anvil/api/app.py` | `TokenizerLoadError` → HTTP 422 exception handler |
| `tests/unit/services/test_inference.py` | Updated for new `LoadedModel` constructor; cache type fix |

## Key decisions

| Decision | Choice |
|----------|--------|
| `bos_id` on protocol | `int \| None` — char returns it, subword returns `None` |
| Export API | Lower-churn: kept `chars` positional, added optional kwargs |
| Old checkpoint compat | Defaults to `"char"`/`"char_json"` via `.get()` |
| Deps | `tokenizers`, `sentencepiece`, `transformers` behind `[finetune]` |

## Vault health

Ran `make vault-audit` — 0 errors. Session log and spec artifacts committed.

## See also

- [[Specs/043 Subword Tokenizer Abstraction/043 Subword Tokenizer Abstraction|043 Subword Tokenizer Abstraction]]
- [[Specs/038 Fine-Tuning Arc/038 Fine-Tuning Arc|038 Fine-Tuning Arc]]
- [[Reference/FineTuningArchitectureDecisions|Fine-Tuning Architecture Decisions]]
