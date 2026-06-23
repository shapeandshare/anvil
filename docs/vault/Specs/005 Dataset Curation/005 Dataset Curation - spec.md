---
title: 005 Dataset Curation - spec
type: spec
tags:
  - type/spec
spec-refs:
  - docs/vault/Specs/005 Dataset Curation/
related:
  - '[[005 Dataset Curation]]'
created: ~
updated: ~
---
# Feature Specification: Dataset Curation

**Feature Branch**: `005-dataset-curation`
**Created**: 2026-06-12
**Status**: Draft
**Input**: User description: "i need feature rich and high fidelity dataset curation capabilities that are easy to use and import and export out of the platform, to CRUD and to use easily with the rest of the project"

## Clarifications

### Session 2026-06-12

- Q: What maximum dataset size should the design support? → A: Up to 1M samples gracefully (100K samples is the performance optimization target)
- Q: When importing into an existing dataset, should data append or replace? → A: Import always appends new samples to existing content
- Q: How should partial import failures be handled? → A: Atomic rollback — failed imports leave no partial data behind
- Q: Can a dataset be deleted when training configs reference it? → A: Block deletion with warning; show which configs depend on it
- Q: Should curation features apply to both file uploads and directory-sourced corpora? → A: All text data sources (uploads + corpora are importable as datasets for curation)
- Q: Spec updated to reflect main branch changes? → A: Merged origin/main (commits: clean minimalist theme, progressive walkthrough). training.html already has a corpus selector; dataset selector added adjacent. CSS changed to minimalist indigo palette — spec updated: User Story 5, FR-025, Assumptions revised.
- Q: Cross-artifact analysis remediation? → A: 3 edits applied: (1) US6 "auto-saves a snapshot" → immutable operation log wording in spec.md; (2) plan.md model path corrected (dataset.py → curation.py); (3) T042 performance benchmark test task added to tasks.md Polish phase; (4) T019 search param clarified to cover FR-019 text search.

## User Scenarios & Testing

### User Story 1 - Browse, Create, and Manage Datasets (Priority: P1)

A researcher opens the Datasets page and sees all their uploaded datasets listed with name, size, row count, and creation date. They can create a new empty dataset, give it a name and description, and immediately see it in the list. They can edit metadata, delete datasets they no longer need, and search or filter by name.

**Why this priority**: CRUD is the foundation everything else builds on. Without the ability to create, view, and manage datasets, no curation or training integration is possible.

**Independent Test**: Can be fully tested by navigating to the Datasets page, creating a new dataset, seeing it appear in the list, editing its name, and deleting it — all without importing any data or using the training pipeline.

**Acceptance Scenarios**:

1. **Given** the user is on the Datasets page, **When** they click "New Dataset" and enter a name, **Then** a new empty dataset appears in the list with a unique identifier.
2. **Given** a dataset exists, **When** the user clicks "Edit" and changes its name or description, **Then** the changes are saved and reflected immediately.
3. **Given** a dataset exists, **When** the user clicks "Delete" and confirms, **Then** the dataset and all its data is removed and no longer appears in the list.
4. **Given** the user has multiple datasets, **When** they type a search query in the filter box, **Then** only datasets whose names match the query are shown.
5. **Given** the user is viewing the Datasets page, **When** the page loads, **Then** each dataset row shows name, row count, total size, and last modified date.

---

### User Story 2 - Import Data from External Sources (Priority: P1)

A researcher has text data from various sources and wants to import it into the platform for training. They can upload files in common formats (plain text, CSV, JSONL, JSON) through the web UI, or import from an existing directory-sourced corpus. The system validates the data during import, reports any issues (malformed rows, encoding problems), and shows a preview before finalizing. Users can also paste raw text directly. Import always appends new samples to the existing dataset — it never replaces or clears existing content.

**Why this priority**: Import is the primary way data enters the system. Without it, no downstream curation or training is possible. Existing `.txt` upload needs to be extended to support richer formats.

**Independent Test**: Can be fully tested by preparing sample files in each supported format, uploading them through the UI, and verifying the imported data appears correctly in the dataset viewer — no curation features or training pipeline needed.

**Acceptance Scenarios**:

1. **Given** the user is viewing a dataset, **When** they click "Import" and select a `.csv` file or an existing corpus, **Then** the data is parsed and a preview of the first 20 rows is shown before the user confirms import.
2. **Given** the user is viewing a dataset, **When** they upload a `.txt` file (single blob), **Then** the file is split by newlines (or configurable delimiter) into individual samples.
3. **Given** the user uploads a malformed file, **When** parsing fails, **Then** the system shows a clear error message describing which rows failed and why.
4. **Given** the user wants to import JSONL data, **When** they upload a `.jsonl` file, **Then** each line is parsed as a separate JSON record and imported as individual samples.
5. **Given** the user wants to import quickly, **When** they paste raw text into a text area, **Then** each line is treated as a separate sample and imported.

---

### User Story 3 - Curate and Clean Dataset Content (Priority: P1)

A researcher needs to clean and refine their dataset before training. They can browse individual samples in a paginated view, search within samples, edit or delete individual entries, and apply bulk operations like deduplication (remove exact or near-duplicate rows), filtering by text length (remove samples shorter/longer than thresholds), and regex-based search-and-replace across all samples. The dataset shows quality metrics: total tokens (estimated), vocabulary size, sample length distribution, and duplicate count.

**Why this priority**: "High fidelity curation" is the core ask. Cleaning and quality control directly impact model training quality. This is where the user gets the most value.

**Independent Test**: Can be tested independently by importing a known messy dataset (with duplicates, outliers, mixed quality), running deduplication and length filters, and confirming the resulting dataset is clean and matches expected counts.

**Acceptance Scenarios**:

1. **Given** a dataset with 1000 samples, **When** the user views the dataset, **Then** samples are shown in a paginated table with sample index, preview text (first 200 chars), and length.
2. **Given** a dataset with duplicate rows, **When** the user clicks "Remove Duplicates", **Then** exact duplicate rows are removed and the user is shown how many were removed.
3. **Given** a dataset, **When** the user sets a minimum length of 50 characters and clicks "Filter", **Then** all samples shorter than 50 characters are removed.
4. **Given** a dataset, **When** the user performs a regex search/replace across all samples, **Then** matching text is replaced and the user is shown how many samples were affected.
5. **Given** a dataset with samples, **When** the user views the quality dashboard, **Then** they see estimated token count, vocabulary size, sample length histogram (min, max, mean), and duplicate count.

---

### User Story 4 - Export Data Out of the Platform (Priority: P2)

A researcher wants to use their curated dataset outside the platform — for example, to share with collaborators or use in a different training environment. They can export the entire dataset or a filtered subset in common formats (TXT, CSV, JSONL). Export preserves the curation state (deduplicated, filtered).

**Why this priority**: The user explicitly asked for "export out of the platform." This is important for data portability. It's P2 because curation and import are higher value than export, but it's still a core requirement.

**Independent Test**: Can be tested by creating a dataset, importing known data, running curation operations, then exporting and verifying the exported file contains the curated data in the expected format.

**Acceptance Scenarios**:

1. **Given** a dataset with curated samples, **When** the user clicks "Export" and selects JSONL format, **Then** a `.jsonl` file is downloaded containing all samples as individual JSON lines.
2. **Given** a dataset, **When** the user exports as TXT, **Then** a plain text file is downloaded with one sample per line.
3. **Given** a dataset, **When** the user exports as CSV, **Then** a CSV file is downloaded with columns for sample index and text content.
4. **Given** a dataset with filters applied, **When** the user exports, **Then** only the visible (filtered) subset is exported.

---

### User Story 5 - Use Curated Datasets in Training Pipeline (Priority: P2)

A researcher has curated a clean dataset and wants to use it directly for model training. The dataset is selectable from the training configuration page (existing `training.html`, which already has a corpus selector). A dataset dropdown is added adjacent to the existing corpus selector. When a dataset is selected, the training pipeline consumes the curated state (post-deduplication, post-filtering). The user can see which dataset was used for each experiment in the MLflow experiment history.

**Why this priority**: The user explicitly asked for datasets to "use easily with the rest of the project." Integration with the existing training pipeline is the primary integration point. It's P2 because CRUD and curation come first, but training integration is the payoff.

**Independent Test**: Can be tested by selecting a curated dataset from the training config page, starting a training run, and verifying the experiment log references the correct curated dataset.

**Acceptance Scenarios**:

1. **Given** the user is on the training dashboard (training.html), **When** they configure a new training run, **Then** a dataset dropdown (alongside the existing corpus selector) shows available curated datasets for selection.
2. **Given** a dataset has curation operations applied, **When** it is selected for training, **Then** the curated (post-processed) version is used — not the raw imported data.
3. **Given** a training run completes, **When** the user views experiment details in MLflow, **Then** the dataset name and version are recorded as experiment parameters.

---

### User Story 6 - View and Compare Dataset Versions (Priority: P3)

A researcher wants to track how a dataset changes over time as they curate it. Each curation operation (import, dedup, filter, replace, edit, delete) records an immutable operation log entry with sample counts before/after. Users can view the history of changes applied to a dataset, compare sample counts before and after each operation, and trace which samples were affected.

**Why this priority**: Versioning adds safety and auditability to the curation process, but it's not essential for the initial workflow. It's a quality-of-life feature for P3.

**Independent Test**: Can be tested by applying multiple curation operations (import, dedup, filter), viewing the change history, and confirming each operation is logged with before/after counts.

**Acceptance Scenarios**:

1. **Given** a dataset with curation history, **When** the user opens the "Version History" panel, **Then** they see a chronological list of every curation operation with timestamp and sample count change.
2. **Given** the user performs a deduplication operation, **When** it completes, **Then** a version entry is recorded showing "Removed N duplicates — from X to Y samples."

---

### Edge Cases

- What happens when a user imports a file with mixed encodings (UTF-8, Latin-1, etc.)? The system should attempt auto-detection and fall back to UTF-8 with warnings.
- How does the system handle extremely large datasets (up to 1M samples)? Import should stream data rather than loading it all into memory at once. The UI should show a progress indicator and handle pagination gracefully. Performance benchmarks target 100K samples; 1M samples must complete without failure though may take proportionally longer.
- What happens when a user exports a dataset and immediately imports it back? Re-import should work correctly — the round-trip must preserve data fidelity.
- How does the system handle empty datasets? Empty datasets should be valid (created with no data, all samples deleted). They should be clearly labeled as empty.
- What happens when a curation operation is in progress and the user navigates away? Long-running operations should either complete in the background or be cancelled gracefully. The user should be warned before navigating away.
- What happens when a user imports a file with no valid samples (all rows malformed)? The system should report the error clearly and not create an empty dataset without warning.
- What happens when an import fails partway through (disk full, connection dropped, encoding crash)? The entire import is rolled back atomically — no partially imported samples remain in the dataset. The user is shown the error and can retry.
- What happens when a user tries to delete a dataset that is referenced by a training configuration? Deletion is blocked with a clear message listing the dependent training configs. The user must reassign or delete those configs first.
- How does the system detect and handle near-duplicate (fuzzy) content? Near-duplicate detection is out of scope for v1; only exact deduplication is required.
- What happens when a user imports the same file twice into the same dataset? Append mode means the samples are duplicated; the user must use deduplication to remove exact duplicates after import.

## Requirements

### Functional Requirements

- **FR-001**: Users MUST be able to create a new dataset with a name, description, and optional initial data source.
- **FR-002**: Users MUST be able to view all their datasets in a list with name, row count, total size, and last-modified timestamp.
- **FR-003**: Users MUST be able to edit dataset metadata (name, description).
- **FR-004**: Users MUST be able to delete a dataset and all its associated data permanently. Deletion MUST be blocked if any training configuration references the dataset; the system MUST display which configs depend on it.
- **FR-005**: Users MUST be able to search and filter datasets by name.
- **FR-006**: Users MUST be able to import data from plain text (`.txt`) files; imported samples append to existing dataset content.
- **FR-007**: Users MUST be able to import data from CSV files (one row = one sample, configurable delimiter); imported samples append to existing dataset content.
- **FR-008**: Users MUST be able to import data from JSONL files (one JSON object per line); imported samples append to existing dataset content.
- **FR-009**: Users MUST be able to import data from JSON files (array of strings or objects); imported samples append to existing dataset content.
- **FR-010**: Users MUST be able to paste raw text directly for import (one line = one sample); imports append to existing dataset content.
- **FR-010b**: Users MUST be able to import data from an existing directory-sourced corpus into a dataset for curation; imported corpus content appends to existing dataset samples.
- **FR-011**: The system MUST validate imported data and report parsing errors with row-level detail. If an import fails during execution, all samples from the failed import MUST be rolled back atomically (no partial data).
- **FR-012**: Users MUST be able to preview imported data (first N rows) before confirming the import.
- **FR-013**: Users MUST be able to browse dataset samples in a paginated view with text preview and length.
- **FR-014**: Users MUST be able to edit individual sample content inline.
- **FR-015**: Users MUST be able to delete individual samples from a dataset.
- **FR-016**: Users MUST be able to remove exact duplicate samples from a dataset.
- **FR-017**: Users MUST be able to filter samples by minimum and/or maximum text length (characters).
- **FR-018**: Users MUST be able to perform regex search and replace across all samples in a dataset.
- **FR-019**: Users MUST be able to filter/search within a dataset by text content (case-sensitive/insensitive search).
- **FR-020**: The dataset view MUST display quality metrics: estimated token count, vocabulary size, sample length distribution (min, max, mean, median), and duplicate count.
- **FR-021**: Users MUST be able to export a dataset as plain text (`.txt`) with one sample per line.
- **FR-022**: Users MUST be able to export a dataset as CSV with index and text columns.
- **FR-023**: Users MUST be able to export a dataset as JSONL with one JSON object per line.
- **FR-024**: Export MUST reflect the current curated state of the dataset (post-deduplication, post-filtering).
- **FR-025**: Users MUST be able to select a curated dataset from the existing training configuration page (`training.html`, which already has a corpus selector dropdown). The dataset selector MUST be adjacent to the existing corpus selector.
- **FR-026**: The training pipeline MUST use the curated dataset state (not raw uploaded data).
- **FR-027**: Experiment parameters logged to MLflow MUST include the dataset name used for training.
- **FR-028**: Long-running import operations (100K+ samples, up to 1M ceiling) MUST show progress to the user.
- **FR-029**: The system MUST auto-detect or allow the user to specify text encoding during import.

### Key Entities

- **Dataset**: A named collection of text samples intended for model training. Has metadata (name, description, created date, last modified date), and maintains a curated state derived from one or more import operations.
- **Sample**: An individual text entry within a dataset. Contains text content, an index/position within the dataset, and metadata (length, import source).
- **Curation Operation**: A recorded transformation applied to a dataset (dedup, bulk filter, bulk replace, individual edit/delete). Each operation captures the type, parameters, before/after sample counts, and timestamp.
- **Import Source**: A reference to an external data source that was imported into a dataset. Tracks the original filename, format, row count imported, and any parsing errors encountered.
- **Export Profile**: A configuration for exporting dataset data, specifying the output format (TXT, CSV, JSONL), and whether to export the full dataset or the currently filtered subset.

## Success Criteria

### Measurable Outcomes

- **SC-001**: A user can import a 10,000-sample CSV file, browse the data, find and remove duplicates, filter by length, and export the result as JSONL — all within a single session without leaving the web UI.
- **SC-002**: A curated dataset can be selected and used for a training run directly from the training configuration page in 3 clicks or fewer.
- **SC-003**: Importing a file with 100,000 samples completes in under 30 seconds (excluding file upload time). Importing up to 1M samples must succeed without failure, with graceful degradation (progress indication, streaming).
- **SC-004**: Exporting a dataset of 10,000 samples completes in under 10 seconds.
- **SC-005**: All curation operations (dedup, filter, replace, delete) give visual feedback (sample count change) within 2 seconds for datasets up to 10,000 samples.
- **SC-006**: A user can complete the full dataset lifecycle — create, import, curate, train, export — without needing to read documentation or consult external resources.
- **SC-007**: Dataset quality metrics (token count, vocabulary, length distribution) are displayed within 3 seconds of opening a dataset with 10,000 samples.
- **SC-008**: A dataset with 1M samples can be imported successfully (with streaming and progress indication) without time limit constraints.

## Assumptions

- Users are researchers or ML practitioners already familiar with the platform's training workflow.
- The existing authentication and session management system handles access control (single-user for initial release).
- Existing upload functionality (`.txt` files) will be extended rather than replaced.
- Existing directory-sourced corpus ingestion can be bridged into the dataset curation system — corpus data will be importable as datasets for curation purposes.
- The existing training pipeline (`training.py`) can be extended to consume curated datasets alongside the current corpus-based ingestion. The existing `training.html` page (with corpus selector, hyperparameter inputs, and SSE streaming) provides the UI integration point — a dataset selector will be added adjacent to the existing corpus selector.
- Maximum dataset capacity is 1M samples. Performance is tuned for 100K samples; datasets up to 1M must operate correctly (streaming, progress indication) though may be slower.
- Text-based models are the primary use case (consistent with the project's GPT training focus).
- Dataset storage uses the existing file storage abstraction (`LocalFileStore`), and large datasets may use a combination of database and filesystem storage.
- Near-duplicate (fuzzy) detection is out of scope for v1; exact string deduplication only.
- The platform serves a single concurrent user (no multi-user dataset isolation needed for v1).
- Dataset versioning (snapshots before destructive operations) is a nice-to-have for v1; essential state is preserved through the existing database.