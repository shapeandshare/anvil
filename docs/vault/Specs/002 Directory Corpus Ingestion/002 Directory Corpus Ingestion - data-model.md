---
title: 002 Directory Corpus Ingestion - data-model
type: data-model
tags:
  - type/spec
spec-refs:
  - docs/vault/Specs/002 Directory Corpus Ingestion/
related:
  - '[[002 Directory Corpus Ingestion]]'
created: ~
updated: ~
---
# Data Model: Directory Corpus Ingestion

**Phase**: Phase 1 — Data Model & Contracts
**Date**: 2026-06-11
**Spec**: `docs/vault/Specs/002 Directory Corpus Ingestion/spec.md`

## Entity Overview

| Entity | Repository | Service | API Prefix |
|--------|-----------|---------|------------|
| Corpus | `CorpusRepository` | `CorpusService` | `/v1/corpora` |
| CorpusFile | (child of CorpusRepository) | `CorpusService` | `/v1/corpora/{id}/files` |
| Document | (transient, not persisted) | `CorpusLoader` | (internal — produced on load) |

---

## Corpus

Top-level entity representing an ingested directory of source files.

| Field | Type | Constraints | Notes |
|-------|------|-------------|-------|
| `id` | int | PK, auto-increment | |
| `name` | str | NOT NULL, unique, 1-255 chars | User-facing label |
| `description` | str | nullable, max 1000 chars | |
| `root_path` | str | NOT NULL | Absolute path to directory |
| `include_patterns` | str | nullable | JSON list of glob patterns (e.g. `["**/*.py"]`). Null = all defaults |
| `exclude_patterns` | str | nullable | JSON list of exclude globs. Merged with defaults |
| `chunking_strategy` | str | NOT NULL, default `"windowed"` | One of: `"line"`, `"windowed"`, `"file"` |
| `chunk_overlap` | float | NOT NULL, default 0.5 | Overlap ratio (0.0-1.0) for windowed strategy |
| `file_count` | int | NOT NULL, default 0 | Number of matched files |
| `document_count` | int | NOT NULL, default 0 | Total chunks produced across all files |
| `language_map` | str | nullable | JSON of `{extension: count}` — file type breakdown |
| `created_at` | datetime | NOT NULL, auto | |
| `updated_at` | datetime | NOT NULL, auto | |

### Validation Rules
- `name` must be unique
- `root_path` must exist and be a directory (validated at ingest time)
- `chunking_strategy` must be one of: `line`, `windowed`, `file`
- `chunk_overlap` must be 0.0-1.0 (only applies to `windowed` strategy)
- `include_patterns` and `exclude_patterns` must be valid JSON arrays of glob strings
- Re-ingestion updates `file_count`, `document_count`, `language_map` (idempotent)

### State Transitions
```
Created (metadata only) → Ingested (files walked + chunked + counted)
                              ↕
                         Re-ingested (re-walk + re-count)
                                   
Deleted → (cascade removes all CorpusFile records)
```

### Relationships
- `corpus_files`: one-to-many with CorpusFile (cascade delete)
- `training_configs`: one-to-many with TrainingConfig (SET NULL on delete)

---

## CorpusFile

Represents a single file within an ingested corpus.

| Field | Type | Constraints | Notes |
|-------|------|-------------|-------|
| `id` | int | PK, auto-increment | |
| `corpus_id` | int | FK → corpus.id, NOT NULL | Parent corpus |
| `relative_path` | str | NOT NULL | Path relative to corpus root |
| `language` | str | nullable | Detected from extension (e.g. "Python") |
| `line_count` | int | nullable | Total lines in file |
| `char_count` | int | nullable | Total characters |
| `chunk_count` | int | nullable | Number of chunks produced from this file |
| `encoding` | str | nullable | Detected encoding (e.g. "utf-8") |
| `size_bytes` | int | nullable | File size on disk |
| `last_modified` | datetime | nullable | mtime at ingest time |
| `created_at` | datetime | NOT NULL, auto | |
| `updated_at` | datetime | NOT NULL, auto | |

### Validation Rules
- `corpus_id` must reference an existing Corpus
- `relative_path` must be unique per corpus
- `language` is derived from file extension (not user-provided)

### Relationships
- `corpus`: many-to-one with Corpus (cascade delete)

---

## Document (Transient)

Represents a single training example derived from a CorpusFile via chunking. NOT persisted — produced on-the-fly by CorpusLoader when training starts.

| Field | Type | Notes |
|-------|------|-------|
| text | str | The chunk text (one training document) |
| source_corpus_id | int | Reference to parent corpus |
| source_file_id | int | Reference to parent CorpusFile |
| chunk_index | int | Position in the chunk sequence for this file |

Documents are produced as `list[str]` for compatibility with the `train()` function signature. Source metadata is stored for traceability but the engine sees plain strings.

---

## TrainingConfig Changes

**MODIFIED** — rename `dataset_id` to `corpus_id` to reflect the new entity:

| Field | Change |
|-------|--------|
| ~~dataset_id~~ | REMOVED |
| `corpus_id` | NEW: FK → corpus.id, nullable |


## Migration: 002_add_corpus_tables

```sql
-- Create corpus table
CREATE TABLE corpora (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR(255) NOT NULL UNIQUE,
    description VARCHAR(1000),
    root_path VARCHAR(500) NOT NULL,
    include_patterns TEXT,
    exclude_patterns TEXT,
    chunking_strategy VARCHAR(20) NOT NULL DEFAULT 'windowed',
    chunk_overlap FLOAT NOT NULL DEFAULT 0.5,
    file_count INTEGER NOT NULL DEFAULT 0,
    document_count INTEGER NOT NULL DEFAULT 0,
    language_map TEXT,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Create corpus_files table
CREATE TABLE corpus_files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    corpus_id INTEGER NOT NULL REFERENCES corpora(id) ON DELETE CASCADE,
    relative_path VARCHAR(1000) NOT NULL,
    language VARCHAR(50),
    line_count INTEGER,
    char_count INTEGER,
    chunk_count INTEGER,
    encoding VARCHAR(20),
    size_bytes INTEGER,
    last_modified DATETIME,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(corpus_id, relative_path)
);

-- Migrate training_configs: add corpus_id FK, keep dataset_id for backward compat
ALTER TABLE training_configs ADD COLUMN corpus_id INTEGER REFERENCES corpora(id);
```