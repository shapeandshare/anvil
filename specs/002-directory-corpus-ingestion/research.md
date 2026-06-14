# Research Report: Directory Corpus Ingestion

**Phase**: Phase 0 — Technology & Pattern Research
**Date**: 2026-06-11
**Spec**: `specs/002-directory-corpus-ingestion/spec.md`

## Overview

Technology decisions resolved via: (1) user clarification (chunking strategies — option A, all three), (2) librarian prior art research (bg_5809c760), (3) existing project patterns and constitution constraints.

---

## 1. File Walking & Directory Filtering

### Decision
Use `pathspec` for gitignore-compatible pattern matching with stdlib `pathlib.Path.rglob()` for directory walking.

### Rationale
- `pathspec` is pure Python, <100KB, no binary deps — fits the project's "lightweight dep" ethos for non-core layers
- `PathSpec.match_tree_files()` handles recursive pattern filtering natively
- Supports .gitignore syntax exactly (spec-compliant)
- Alternatives considered: `gitignore_parser` (simpler but less featureful), `py-walk` (adds another dep), custom glob (reinventing wheel)
- Standard directories (`.git/`, `node_modules/`, `venv/`, `__pycache__/`) handled via default pattern list passed to pathspec

### References
- pathspec docs: https://github.com/cpburnz/python-pathspec
- Prior art: Sievio, AIWG Training, DataTrove all use similar pattern-based filtering

---

## 2. Chunking Strategies

### Decision
Three custom chunker implementations in `anvil/services/chunking/`, no external chunking library.

### Rationale
- All three strategies (line-as-doc, fixed-size windowed, file-as-doc) are algorithmically trivial — a library adds unnecessary dependency weight
- Educational Clarity (Constitution Article II) favors readable self-contained code
- AST-based chunking (via `chonkie` or `astchunk`) was evaluated but deferred — the character-level model operates on raw characters, not AST nodes; AST chunking adds complexity without clear benefit at this block_size scale
- Prior art: RecursiveCharacterTextSplitter (LangChain) and sliding window approaches (Mistral Codestral) confirm the windowed approach is standard

### Implementation Plan
- **LineAsDocChunker**: Split on `\n`, strip, filter empty — replicates current `input.txt` behavior exactly
- **FixedSizeWindowChunker**: Sliding window of `block_size` chars with configurable overlap ratio (default 50%)
- **FileAsDocChunker**: Read entire file as one string — truncated to `block_size` by the training loop's `min(block_size, len(tokens) - 1)`

---

## 3. Corpus Storage Strategy

### Decision
Store corpus file metadata and chunk references in SQLite (via new Corpus/CorpusFile tables). Source files are NOT copied to FileStore — the original directory path is referenced. This is a "reference snapshot" rather than a "copy snapshot."

### Rationale
- v1 is single-user local tool — original files are stable by assumption
- Copying to FileStore doubles disk usage for no benefit at this scale
- Simpler: ingest = walk + chunk + record metadata; no file blob storage needed
- Re-ingestion = re-walk (idempotent); no stale copy problem
- If reproducibility requires file snapshots in the future, that's a v2 concern

### Alternatives Considered
- Copy files to `FileStore` (more complex, disk waste, but self-contained) — deferred
- Store chunks as pre-tokenized arrays in DB (over-engineered for this scale) — deferred

---

## 4. Language Detection

### Decision
File extension → language mapping dict. No external language detection library.

### Rationale
- Trivially implemented: `{".py": "Python", ".js": "JavaScript", ...}`
- No need for a library when the mapping is deterministic and the project knows what languages it expects
- Used only for display in corpus browser (User Story 4), not for any functional logic

---

## 5. Dependency Impact

### Decision
Add `pathspec` to project dependencies.

### Rationale
- Pure Python, permissively licensed (MPL 2.0 / LGPL 3+)
- Single dependency addition — no transitive deps
- Used only in `services/chunking/` — never in `core/` (constitution compliant)
- Existing project deps (FastAPI, SQLAlchemy, aiofiles) remain unchanged

---

## 6. Training Integration

### Decision
The existing `TrainingConfig.dataset_id` FK on the `datasets` table is repurposed/aliased to reference a `Corpus` instead. The `_load_docs()` method gains a `corpus_id` parameter; when provided, it delegates to `CorpusService.load_docs()` instead of reading `input.txt`.

### Rationale
- `TrainingConfig` already has a `dataset_id` FK — schema change is minimal (rename to `corpus_id` or add a new FK)
- The `train()` function in `core/engine.py` accepts `list[str]` — both old and new data loading produce the same format
- Backward compatible: if `corpus_id` is None, fall back to `input.txt`

### Alternatives Considered
- Wrapping corpus docs in a new Dataset-like entity — unnecessary indirection, the `train()` function doesn't care about source
- Pass chunks through a streaming generator — over-engineering for single-user local use

---

## 7. CLI Design

### Decision
New `anvil corpus` subcommand group under the existing CLI.

### Patterns
```
microgpt corpus create ./path/to/repo --name "my-corpus" --pattern "**/*.py" --ignore "tests/"
microgpt corpus list
microgpt corpus show <id>
microgpt corpus delete <id>
microgpt corpus ingest <id>          # re-ingest (re-walk + re-chunk)
```

### Rationale
- Follows the existing `anvil train` / `anvil serve` CLI pattern
- Separate subcommand keeps concerns clean
- `ingest` is explicit (not automatic on create) — gives user control