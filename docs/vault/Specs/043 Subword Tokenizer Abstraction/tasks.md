---
title: Tasks — Subword Tokenizer Abstraction
type: spec
tags:
  - type/spec
created: '2026-06-28'
updated: '2026-06-28'
---
# Tasks: Subword Tokenizer Abstraction

**Input**: Design documents from `docs/vault/Specs/043 Subword Tokenizer Abstraction/`
**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to
- Include exact file paths in descriptions

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Dependency setup required before any foundational work

- [x] T001 Add `[finetune]` extra to `pyproject.toml` under `[project.optional-dependencies]` with `tokenizers>=0.15`, `sentencepiece>=0.1.99`, and `transformers>=4.30.0` (transformers included per AGENTS.md Active Technologies note for AutoTokenizer convenience; verify these are NOT in core `[project.dependencies]`)

**Checkpoint**: Dependencies declared — `pip install -e ".[finetune]"` installs subword deps

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before the user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [x] T002 Create `Tokenizer` ABC protocol in `anvil/core/_tokenizer_base.py` — stdlib-only, zero deps. Methods: `encode(text: str) -> list[int]`, `decode(ids: list[int]) -> str`; properties: `vocab_size -> int`, `bos_id -> int | None` (char-level returns its BOS id; subword returns `None` since BOS is a named special token handled internally by `decode()`)
- [x] T003 [P] Create `TokenizerFamily` (`CHAR`, `SUBWORD`) `StrEnum` in `anvil/services/_shared/tokenizer_family.py` AND `SerializationType` (`CHAR_JSON`, `HF_FAST`, `SENTENCEPIECE`) `StrEnum` in `anvil/services/_shared/serialization_type.py` — separate files per one-class-per-file rule (follows the existing `_shared/device_type.py` convention)
- [x] T004 [P] Create `TokenizerLoadError` exception class in `anvil/services/_shared/tokenizer_load_error.py` — a plain `Exception` subclass (NOT Pydantic `BaseModel`; exceptions must subclass `Exception`) with `message: str`, `file_path: str | None`, `cause: str | None` attributes, formatting them into the exception message
- [x] T005 [P] Confirm existing package structure: `anvil/services/_shared/__init__.py`, `anvil/services/inference/__init__.py`, and `anvil/core/__init__.py` all exist (they do — no new package-init needed). Tests follow the FLAT convention `tests/unit/services/test_*.py` and `tests/unit/core/test_*.py` (NOT nested `services/inference/`)

**Checkpoint**: Foundation ready — protocol, two enums (separate files), error type; existing package structure confirmed

---

## Phase 3: User Story 1 — A Model Tokenizes With Its Own Tokenizer (Priority: P1) 🎯 MVP

**Goal**: Encode/decode for any model resolves from the tokenizer attached to that model — char-level for native models, subword for imported HF models — with no caller assuming a fixed scheme.

**Independent Test**:
1. Round-trip encode→decode arbitrary text through char-level `Vocabulary` implementing the protocol → reproduces input exactly
2. Round-trip encode→decode through a TinyLlama subword tokenizer via the same protocol → reproduces input exactly
3. Existing char-level training/inference paths are byte-for-byte unchanged (contract tests T016, T017)
4. Model info endpoint returns `tokenizer` metadata (family, serialization_type, vocab_size)

### Implementation for User Story 1

> ⚠️ **TDD Order**: Tasks are grouped by type below, but execution MUST follow Red-Green-Refactor (Article IV). Write the test tasks (T020–T023) FIRST, verify they FAIL on the pre-refactor code, THEN implement the corresponding production code (T006–T019). After implementation, tests MUST pass. Note: T020 (char-level parity) should be captured against the CURRENT `Vocabulary` before refactoring, so it locks in the byte-for-byte baseline.

#### Core protocol + implementations

- [x] T006 [US1] Update `Vocabulary` in `anvil/core/vocabulary.py` to inherit from `Tokenizer` protocol — add `class Vocabulary(Tokenizer)`; existing `encode`/`decode`/`vocab_size`/`bos_id` already match the interface; add a `chars` property returning `self.chars` (the char list). Import `Tokenizer` from `._tokenizer_base`
- [x] T007 [P] [US1] Create `HFFastTokenizer` class in `anvil/services/inference/_subword_tokenizer.py` wrapping `tokenizers.Tokenizer.from_file("tokenizer.json")` — implement `encode` (extract `.ids` from `Encoding`), `decode` (with `skip_special_tokens=True`), `vocab_size` (via `get_vocab_size(with_added_tokens=True)`), `bos_id` returns `None`. Module-level `try/except ImportError` per AGENTS.md Principle 14 (optional dependency)
- [x] T008 [P] [US1] Create `SentencePieceTokenizer` class in `anvil/services/inference/_subword_tokenizer.py` wrapping `sentencepiece.SentencePieceProcessor` — implement `encode` (`processor.encode(text)`), `decode` (`processor.decode(ids)`), `vocab_size` (`processor.get_piece_size()`), `bos_id` returns `None`. Module-level `try/except ImportError` for optional dep. NOTE: one class per file (Article §10.7) — if both wrappers cannot share a file, split `SentencePieceTokenizer` into `_sentencepiece_tokenizer.py`

#### Tokenizer persistence + factory (THE DISPATCH LINCHPIN)

- [x] T009 [US1] Extend `LlamaModel.save()`/`load()` in `anvil/core/engine.py` — persist `tokenizer_family` and `serialization_type` in the model JSON alongside `chars` (default `tokenizer_family="char"`, `serialization_type="char_json"` for backward compat when absent on load). On `load()`, read both with `.get()` defaults so pre-existing `experiment_*.json` files still load (NMRG). Use the `TokenizerFamily`/`SerializationType` string values (stdlib-only — store as plain strings in JSON, core has no enum-import constraint violation since enums are in services; store the raw `str` values, e.g. `"char"`, `"char_json"`)
- [x] T010 [US1] Create `TokenizerFactory` (loader) in `anvil/services/inference/tokenizer_factory.py` — given a model's `tokenizer_family` + `serialization_type` + `chars` + artifact directory, return a `Tokenizer`: `char_json` → `Vocabulary.from_chars(chars)`; `hf_fast` → `HFFastTokenizer` from `tokenizer.json`; `sentencepiece` → `SentencePieceTokenizer` from `.model`; unknown/unsupported → raise `TokenizerLoadError`. Catch corrupt-file/missing-file errors and re-raise as `TokenizerLoadError` with `file_path` + `cause`. Log family + serialization type at INFO on load (FR-015b)

#### LoadedModel + call-site migration

- [x] T011 [US1] Update `LoadedModel` in `anvil/services/inference/loaded_model.py` — change constructor to accept `tokenizer: Tokenizer` instead of `chars: list[str]`; add a `chars` property returning `tokenizer.chars` for char-level (via `getattr(tokenizer, "chars", [])`) or `[]` for subword; add a `bos_id` property delegating to `tokenizer.bos_id`; replace `self.vocab = Vocabulary.from_chars(chars)` with `self.tokenizer`. Update `info()` to include `tokenizer` metadata (family, serialization_type, vocab_size)
- [x] T012 [US1] Update `InferenceService` in `anvil/services/inference/inference.py` — at the 3 `LoadedModel(...)` construction sites (lines ~168, ~178, ~217), build the tokenizer via `TokenizerFactory` from the loaded model's recorded family; replace all `loaded.vocab.encode(text)` → `loaded.tokenizer.encode(text)` (7 sites), `loaded.vocab.bos_id` → `loaded.bos_id` (~12 sites; the `i != bos_id` display checks must treat `bos_id is None` as "never BOS"), `loaded.vocab.vocab_size` → `loaded.tokenizer.vocab_size` (~4 sites). Keep `loaded.chars[i]` display labels working
- [x] T013 [US1] Update `anvil/services/inference/demo_model_provider.py` — `_warmup` path (`model.save(..., uchars)`, line ~257-258) and `DemoModelProvider.get_model()` (returns `tuple[LlamaModel, list[str]]`, lines ~292-333): keep `get_model()` returning `(model, chars)` for backward compat, but ensure callers can build a `Vocabulary` tokenizer from those chars. Update the `export_svc.export(model, tmpdir, uchars)` call (line ~214) for the new export signature (see T015)

#### Export migration (ALL call sites)

- [x] T014 [US1] Update `SafetensorsExportService.export()` AND `retry_export()` in `anvil/services/training/export.py` — change `export()` to accept `tokenizer: Tokenizer` (or keep `chars: list[str]` + add `tokenizer_family`/`serialization_type` params — choose the lower-churn option); write `tokenizer_family` + `serialization_type` into `config.json`. For subword tokenizers, set `generate_tokenizer()` `"type": "SubwordTokenizer"`, skip char-level `vocab`/`chars`, and copy the subword files (`tokenizer.json`/`tokenizer.model`) flat into the output dir. Update `retry_export()` (line ~302-327) which calls `self.export(model, output_dir, chars)` with `chars = model.chars or []`
- [x] T015 [P] [US1] Update all 5 export call sites for the new signature: the 4 `export()` callers — `anvil/services/compute/modal_backend.py:308`, `anvil/services/inference/demo_model_provider.py:214`, `anvil/cli.py:355`, `anvil/api/v1/training.py:706` — plus the `retry_export()` caller `anvil/api/v1/experiments.py:837`. Each currently passes positional `uchars`; update to match T014's chosen signature
- [x] T016 [P] [US1] Update `eval.py` and `learning.py` — `eval.py:57` (`chars = loaded.chars`), `eval.py:86` (`model.vocab_size`), `learning.py` (`loaded.chars`, `model.vocab_size`): `loaded.chars` still works (property); keep `model.vocab_size` as model hyperparameter (unchanged — it is the embedding-table size, not a tokenizer concern)
- [x] T017 [P] [US1] Update API routes in `anvil/api/v1/` — surface `tokenizer` metadata (family, serialization_type, vocab_size) from `LoadedModel.info()` in model info responses (per contracts/api-dispatch.md)
- [x] T018 [US1] Add INFO-level logging per FR-015b in `inference.py` and `tokenizer_factory.py` — logger named `anvil.services.inference.tokenizer`; log family + serialization type at load time (T010) and on each encode/decode dispatch
- [x] T019 [US1] Map `TokenizerLoadError` to HTTP 422/500 in the API error handler (per contracts/api-dispatch.md) — locate the existing exception handler in `anvil/api/` and add a branch, or add a FastAPI exception handler for `TokenizerLoadError`

#### Tests (write FIRST per TDD order)

- [x] T020 [US1] Write contract tests: char-level encode/decode parity (byte-for-byte same as pre-abstraction `Vocabulary`) in `tests/unit/core/test_tokenizer_protocol.py` (char-level `Vocabulary`/`Tokenizer` live in `anvil/core/`, so tests follow `tests/unit/core/` per existing convention alongside `test_tokenizer.py`)
- [x] T021 [US1] Write contract tests for unicode edge cases: emoji (surrogate pairs), CJK ideographs, combining diacritics, null character in `tests/unit/core/test_tokenizer_protocol.py`
- [x] T022 [US1] Write subword tokenizer round-trip test: load a TinyLlama-compatible `tokenizer.json` via `HFFastTokenizer`, verify encode→decode reproduces input, using `pytest.mark.skipif` gated on `[finetune]` extra availability in `tests/unit/services/test_subword_tokenizer.py` (flat services convention)
- [x] T023 [US1] Write `TokenizerFactory` error path tests: corrupt `tokenizer.json`, missing file, unknown family, unsupported serialization type — all raise `TokenizerLoadError`. Also a NMRG test: an old `experiment_*.json` with no `tokenizer_family` field loads as `char`/`char_json`. In `tests/unit/services/test_tokenizer_factory.py`

**Checkpoint**: At this point, User Story 1 should be fully functional:
- `LlamaModel` persists and reloads its tokenizer family/serialization type (with char defaults for old files)
- `TokenizerFactory` dispatches on the recorded family to produce the right `Tokenizer`
- Native models use char-level tokenizer via the protocol (same behavior as before)
- Imported HF models use subword tokenizer (behind `[finetune]` extra)
- All 5 export call sites + retry_export updated — no broken signatures (NMRG SC-004)
- Contract tests prove char-level parity; old checkpoints still load
- All pre-existing tests pass unmodified (NMRG SC-004)

---

## Phase 4: Polish & Cross-Cutting Concerns

**Purpose**: Final validation and cleanup

- [x] T024 Run `make lint` — 14 pre-existing failures in governance/corpora/tracking (unrelated); zero in tokenizer code
- [x] T025 Run `make typecheck` (mypy --strict)
- [x] T026 Run `make test` — 172 relevant tests pass (NMRG: unrelated 14 pre-existing failures remain unchanged)
- [x] T027 Final review: base install imports anvil OK; _subword_tokenizer behind finetune extra; INFO logging confirmed; TokenizerLoadError unmapped handler removed (handled in app.py exception handler)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion — BLOCKS all user stories
- **User Stories (Phase 3)**: Depends on Foundational phase completion
- **Polish (Final Phase)**: Depends on all desired phases being complete

### User Story Dependencies

- **User Story 1 (P1)**: Can start after Foundational (Phase 2) — this is the only user story

### Within Each Phase

- Tasks without `[P]` marker must be done sequentially
- `[P]` tasks can run in parallel (different files, no cross-dependencies)

### Parallel Opportunities

| Parallel Group | Tasks | Files |
|---------------|-------|-------|
| Foundational enums/error | T003, T004, T005 | separate `_shared/` files |
| Subword wrappers | T007, T008 | `_subword_tokenizer.py` (or split per one-class-per-file) |
| Export call-site fan-out | T015 | `modal_backend.py`, `cli.py`, `training.py`, `experiments.py` |
| Downstream call sites | T016, T017 | `eval.py`, `learning.py`, API routes |
| Contract tests | T020, T021, T023 | Test files (different test methods) |
| Subword tests | T022 | `_subword_tokenizer.py` tests |

> **NOT parallel**: T009 (engine save/load) → T010 (factory depends on it) → T011 (LoadedModel) → T012 (inference uses factory). These form the critical dispatch chain and must be sequential. T014 (export signature) must precede T015 (call sites).

---

## Parallel Example: User Story 1

```bash
# Launch wrappers in parallel:
Task: "Create HFFastTokenizer in anvil/services/inference/_subword_tokenizer.py"
Task: "Create SentencePieceTokenizer wrapper"

# After T014 (export signature), fan out the call-site updates in parallel:
Task: "Update modal_backend.py export call"
Task: "Update cli.py export call"
Task: "Update training.py + experiments.py export/retry_export calls"

# Write contract tests in parallel (FIRST, per TDD):
Task: "Write char-level parity contract tests"
Task: "Write unicode edge case contract tests"
Task: "Write TokenizerFactory error path + NMRG-old-checkpoint tests"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup → `[finetune]` extra in pyproject.toml (T001)
2. Complete Phase 2: Foundational → protocol (+bos_id), enums, error type (T002-T005)
3. Complete Phase 3: User Story 1 → all implementation + test tasks (T006-T023)
4. **STOP and VALIDATE**: Run `make test` — all pre-existing tests pass (NMRG), new contract tests pass
5. Run `make lint && make typecheck`

### Incremental Delivery

1. Setup + Foundational → infrastructure ready (T001-T005)
2. Protocol + impls (T006-T008) → `Vocabulary` implements `Tokenizer`, subword wrappers exist
3. **Dispatch chain** (T009→T010→T011→T012) → persistence + factory + LoadedModel + inference (CRITICAL PATH, sequential)
4. Provider + export migration (T013-T017) → all production code uses the protocol; all export call sites fixed
5. Logging + error mapping (T018-T019)
6. Tests + validation (T020-T023) → contract tests prove parity, old checkpoints load
7. Polish (T024-T027) → lint/typecheck/test pass

### Key Risks

- **Invariant risk**: Char-level behavior MUST be byte-for-byte identical. T020 contract tests are critical — run them before and after the refactor to prove parity.
- **Backward-compat checkpoints**: Old `experiment_*.json` files have no `tokenizer_family` field. T009 MUST default to `char`/`char_json` on load; T023 verifies this (NMRG).
- **Export signature fan-out**: 5 call sites (4 `export` + 1 `retry_export`) pass `uchars` positionally today. T014/T015 must update ALL of them or `make test` breaks.
- **Import gating**: `_subword_tokenizer` must NOT break base install. T027 verifies `import anvil` + char-level load works without `[finetune]`.
- **BOS handling**: Subword `bos_id` is `None`. All ~12 `loaded.vocab.bos_id` display checks in `inference.py` must treat `None` as "never BOS" (T012).

---

## Notes

- [P] tasks = different files, no dependencies
- [US1] label maps task to User Story 1 for traceability
- Each task should be independently completable
- The dispatch chain T009→T010→T011→T012 is the linchpin — without persistence (T009) and factory (T010), the recorded `TokenizerFamily` has no effect (SC-003)
- `Vocabulary` may import the `Tokenizer` protocol; one-class-per-file is preserved (protocol lives in its own `_tokenizer_base.py`)
- The two subword wrappers (T007/T008) may need separate files per Article §10.7 one-class-per-file — split if lint flags it
- Stop after Phase 3 to validate MVP independently