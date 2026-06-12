# Feature Specification: Directory Corpus Ingestion

**Feature Branch**: `002-directory-corpus-ingestion`
**Created**: 2026-06-11
**Status**: Draft
**Input**: User description: Support directory structures as training corpora for microgpt — ingest entire source code directories with file pattern filtering, ignore rules, and configurable chunking strategies as training data for the model. Currently only single .txt files are supported.

## User Scenarios & Testing

### User Story 1 - Ingest a Source Code Directory for Training (Priority: P1)

A user who wants to train the model on their own source code can point the system at a directory of source files and have those files automatically ingested, chunked, and made available for training runs.

**Why this priority**: This is the core value of the feature — without ingestion, users can't use directory-based corpora at all.

**Independent Test**: Can be fully tested by pointing the system at a small directory of source files and verifying that the corpus appears in the dataset list with the expected file count and document count.

**Acceptance Scenarios**:

1. **Given** a directory containing 5 source files (`.py`, `.js`, `.md`), **When** the user initiates ingestion of that directory, **Then** all 5 files are processed and the corpus shows a document count equal to the total number of chunks extracted from all files.
2. **Given** a directory with a `.git` subdirectory and `node_modules/`, **When** the user ingests the directory, **Then** those standard ignore directories are excluded and not counted in the corpus.
3. **Given** a directory containing binary files (`.png`, `.exe`), **When** the user ingests the directory, **Then** only text-based source files are processed and binary files are skipped.

---

### User Story 2 - Configure File Patterns and Ignore Rules (Priority: P2)

Users can specify which file types to include (e.g., only `*.py` files) and which paths to exclude, so they can curate the training data to focus on relevant code.

**Why this priority**: Pattern filtering gives users control over what goes into training, which is important for quality but not required for the basic ingestion flow.

**Independent Test**: Can be tested by ingesting a directory with mixed file types while specifying include/exclude patterns, then verifying only matching files appear in the corpus.

**Acceptance Scenarios**:

1. **Given** a directory with `.py`, `.js`, and `.md` files, **When** the user configures the corpus to include only `*.py` files, **Then** only the `.py` files appear in the ingested corpus.
2. **Given** a directory with a `tests/` subdirectory, **When** the user specifies an ignore rule for `tests/`, **Then** files under `tests/` are excluded from the corpus.
3. **Given** no explicit file patterns are configured, **When** the user ingests a directory, **Then** common source file types (`.py`, `.js`, `.ts`, `.go`, `.rs`, `.java`, `.md`, `.txt`, `.yaml`, `.json`, `.css`, `.html`) are included by default and binary files are excluded.

---

### User Story 3 - Select a Directory Corpus for a Training Run (Priority: P2)

Users can choose an ingested directory corpus (rather than a single-file dataset) when starting a training run, and the system uses that corpus as the training data.

**Why this priority**: This closes the loop — ingestion alone is useless if you can't train on it. This must work for the feature to deliver value.

**Independent Test**: Can be tested by creating a corpus, starting a training run with it selected, and verifying the training progresses using data from that corpus.

**Acceptance Scenarios**:

1. **Given** a directory corpus has been ingested, **When** the user starts a training run and selects that corpus, **Then** the training proceeds using documents derived from the corpus files.
2. **Given** a training run in progress using a directory corpus, **When** the user views the loss telemetry, **Then** the training progresses normally without errors.

---

### User Story 4 - View Corpus Contents and Statistics (Priority: P3)

Users can browse the files within a directory corpus, seeing per-file stats (line count, character count, language) and overall corpus statistics.

**Why this priority**: Transparency into what data is being trained on is valuable for debugging and quality assurance, but not required for the feature to function.

**Independent Test**: Can be tested by ingesting a small directory, navigating to the corpus view, and verifying all files are listed with correct stats.

**Acceptance Scenarios**:

1. **Given** an ingested corpus from a directory with 3 files, **When** the user views corpus details, **Then** all 3 files are listed with their relative paths, line counts, and detected languages.
2. **Given** an ingested corpus, **When** the user views the corpus summary, **Then** the total file count, total document count, and file type breakdown are displayed.

---

### Edge Cases

- What happens when an ingested directory has zero matching files (due to strict pattern filtering or empty directory)?
- How does the system handle very large directories (10,000+ files)? Should there be a file count limit or progress indication?
- What happens to existing corpora when a directory is re-ingested (update vs replace)?
- How does the system handle files with mixed encodings (UTF-8, UTF-16, latin-1)?
- What happens if a corpus is deleted while a training run referencing it is in progress?
- Should symlinks pointing outside the corpus root directory be followed or skipped?

## Requirements

### Functional Requirements

- **FR-001**: Users MUST be able to initiate ingestion of a local directory as a training corpus, specifying the directory path.
- **FR-002**: The system MUST recursively walk the directory tree, applying file pattern inclusion filters and ignore rules.
- **FR-003**: The system MUST automatically ignore common non-source directories (`.git/`, `node_modules/`, `venv/`, `__pycache__/`, `.hg/`, `.svn/`, build artifacts).
- **FR-004**: The system MUST support configurable include patterns (e.g., `**/*.py`) and exclude patterns (e.g., `tests/`).
- **FR-005**: The system MUST chunk each source file into training documents using the corpus's configured chunking strategy (line-as-doc, fixed-size windowed chunks, or file-as-doc), with documents sized to fit within the model's configured `block_size`.
- **FR-006**: The system MUST report corpus statistics: total files, total documents, file type distribution, and per-file line/character counts.
- **FR-007**: Users MUST be able to select an ingested directory corpus as the data source when starting a training run.
- **FR-008**: The system MUST persist the corpus metadata (files, patterns, stats) so it survives application restarts.
- **FR-009**: Users MUST be able to delete a corpus and its associated ingested files.
- **FR-010**: The system MUST handle files with non-UTF-8 encodings gracefully (skip with a warning, continue processing remaining files).
- **FR-011**: Three chunking strategies MUST be supported, configurable per-corpus at creation time: (a) line-as-doc — each non-empty source line is one document (backward compatible), (b) fixed-size windowed chunks — files are split into `block_size` character windows with configurable overlap (default 50%), (c) file-as-doc — the entire file content is treated as a single document (subject to `block_size` truncation).

### Key Entities

- **Corpus**: A named collection of source files ingested from a directory. Has a root path, include/exclude patterns, chunking strategy, and aggregate statistics (file count, doc count, language breakdown).
- **CorpusFile**: An individual file within a corpus. Records relative path, detected language, line count, character count, and processing status.
- **Document**: A training example derived from a CorpusFile via chunking. Linked to its source file and corpus.

## Success Criteria

### Measurable Outcomes

- **SC-001**: Users can ingest a directory of 100 source files (average 200 lines each) and begin training on the resulting corpus within 30 seconds of initiating ingestion (file I/O bound; larger directories scale linearly).
- **SC-002**: Users can configure include/exclude patterns and verify that only matching files appear in the corpus, with no manual curation needed.
- **SC-003**: A training run using a directory corpus produces comparable loss curves to a training run using an equivalent line-based `.txt` dataset of the same content.
- **SC-004**: Users can browse corpus contents and see per-file stats (relative path, line count, language) for all files, with no missing or duplicated entries.
- **SC-005**: The system correctly excludes standard directories (`.git/`, `node_modules/`, `venv/`, `__pycache__/`) without requiring the user to configure them.

## Assumptions

- Users primarily want to train on source code repositories (Python, JavaScript, TypeScript, Go, Rust, etc.) but the feature should work for any text-based directory.
- The character-level model will continue to be the target; chunking strategies will adapt documents to fit within `block_size`.
- The file ingestion is a one-time import (snapshot), not a live sync. Re-ingestion creates a new corpus version.
- Users have local filesystem access to the directories they want to ingest. Remote/clone-based ingestion is out of scope for v1.
- The default chunking strategy is windowed fixed-size chunks with 50% overlap, which gives the best balance for source code patterns.
- Binary file detection is done by attempting UTF-8 decode and falling back to file extension heuristics.