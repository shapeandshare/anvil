# Feature Specification: Bootstrap Demo Datasets

**Feature Branch**: `009-bootstrap-datasets`  
**Created**: 2026-06-14  
**Status**: Draft  
**Input**: User description: "we currently have a simple hardcoded dataset in train, lets remove that. to replace this we want to craft several premade datasets and corpuses that we can curate here in the repo and use to bootstrap the system for demo purposes"

## User Scenarios & Testing

### User Story 1 - Train on a Premade Demo Corpus Out of the Box (Priority: P1)

A new user clones the repo, runs `make setup` and `make run`, opens the web UI, and can immediately start training on a curated demo corpus without needing to find or upload their own data. The system ships with several corpora (directory-based) and datasets (.txt uploads) that showcase different training behaviors across sizes and domains.

**Why this priority**: This is the core purpose of the feature. Bootstrapping the demo experience is the primary goal.

**Independent Test**: Can be fully tested by running `anvil train` (or clicking "Train" in the UI) without specifying a dataset or corpus — training starts immediately using a bundled demo dataset instead of failing or falling back to an external download.

**Acceptance Scenarios**:

1. **Given** a fresh install with no datasets imported, **When** a user starts a training run with no dataset or corpus specified, **Then** training proceeds using a bundled demo dataset and produces reasonable output
2. **Given** the bundled demo datasets are present in the repository, **When** a user lists available corpora or datasets via `anvil corpus list` or the `/datasets` API, **Then** the demo datasets appear in the list and can be selected for training
3. **Given** a user has specified a particular dataset or corpus for training (not the default), **When** training starts, **Then** the specified dataset is used instead of the default demo dataset

---

### User Story 2 - Select from Multiple Demo Datasets (Priority: P2)

A user exploring the system can choose from multiple premade datasets (e.g., names list, Shakespeare excerpt, math facts) to see how different training data affects the model's output behavior.

**Why this priority**: Multiple datasets demonstrate the system's versatility and make the demo more educational.

**Independent Test**: Can be tested by training on each demo dataset independently and observing that the generated samples reflect each dataset's domain.

**Acceptance Scenarios**:

1. **Given** two different demo datasets are bundled (e.g., names vs. math facts), **When** a user trains a model on each, **Then** the generated samples clearly reflect the domain of the chosen dataset
2. **Given** a user has selected a specific demo dataset for training, **When** the training completes, **Then** the experiment metadata records which dataset was used

---

### User Story 3 - Datasets are Citable and Reproducible (Priority: P3)

A user reviewing an experiment can see exactly which dataset version was used, and another user can reproduce the same experiment by selecting the same dataset.

**Why this priority**: Reproducibility is a core value of the experiment tracking system.

**Independent Test**: Can be tested by re-running an experiment with the same dataset ID and comparing results.

**Acceptance Scenarios**:

1. **Given** an experiment was run using a demo dataset, **When** a user views the experiment details, **Then** the dataset name and ID are clearly displayed
2. **Given** a user has imported a demo dataset into the system, **When** they delete and re-import it, **Then** the dataset content is identical to the original

---

### Edge Cases

- What happens when the `data/demo/` directory is missing or corrupted? The system should report a clear error and suggest running `make setup` or a dedicated bootstrap command.
- What happens when a user has created their own corpora/datasets in addition to the demo ones? Both should coexist without conflict — demo items are clearly labeled (FR-006).
- What happens when a corpus ingestion partially fails (e.g., some files are unreadable)? The bootstrap should report which files failed and continue with the rest, then surface errors to the user.
- How does the system handle large demo files that might bloat the git repository? Demo files should remain under ~500 KB total in the repo.

## Clarifications

### Session 2026-06-14

- Q: How should the bootstrap detect previously-imported demo datasets for idempotency? → A: Match by dataset name (if a dataset with the same name already exists, skip importing it)
- Q: Can users delete demo datasets, and what happens on re-bootstrap after deletion? → A: Allow deletion with a warning; on re-bootstrap the dataset is re-created since the name is now free
- Q: What demo data should ship and how should it be organized? → A: Directory-based corpora as primary format, .txt dataset uploads as secondary. Matrix across 3 sizes × 4 domains (names, prose, structured, code), using public-domain or generated content. Roughly 10 source files, ~500 KB total.

## Requirements

### Out of Scope

- Large-scale automated dataset downloaders or scrapers
- Support for binary/non-text demo files (images, audio)
- Cloud-hosted dataset repositories — all demo data ships in-repo

### Functional Requirements

- **FR-001**: The system MUST ship with demo data covering 3 sizes (small ~1-10KB, medium ~10-100KB, large ~100-500KB) across 4 domains (names, prose/literature, structured/records, code). **Primary delivery format MUST be directories of files ingested as corpora** (using the existing corpus ingestion pipeline). A secondary `.txt` dataset upload path is also supported for demo purposes.
- **FR-001a**: The demo contents MUST use public-domain, generated, or permissively-licensed source material. Suggested sources: Project Gutenberg (public domain), hand-crafted/generated content (no licensing issues), Karpathy's names list (MIT), US government works (public domain).
- **FR-002**: The system MUST remove the hardcoded fallback that downloads `names.txt` from an external URL when no dataset or corpus is specified
- **FR-003**: When no dataset or corpus is explicitly selected for training, the system MUST automatically use a designated default demo dataset
- **FR-004**: Demo datasets MUST be importable into the dataset/corpus management system via a bootstrap command or setup step (e.g., `make setup` or `anvil bootstrap-datasets`)
- **FR-005**: Demo datasets MUST persist in the database so they remain available across server restarts
- **FR-006**: The system MUST clearly label or distinguish demo datasets from user-created datasets (e.g., by naming convention or metadata tag)
- **FR-007**: Removing the hardcoded external download MUST NOT break the training flow for existing users who rely on corpus_id or dataset_id being explicitly provided
- **FR-008**: Demo datasets MUST be detectable — the bootstrap command should be idempotent (running it twice should not create duplicate demo entries). Idempotency check MUST be by dataset name — if a dataset with the same name already exists, the bootstrap MUST skip that entry.
- **FR-009**: Users MUST be able to delete demo datasets via the normal deletion UI/API, but the system SHOULD present a warning that this is a bundled dataset and the deletion is reversible via re-bootstrap. The warning mechanism: the DELETE endpoint (`/datasets/{id}`) checks if the dataset name starts with `"Demo - "` and, if so, returns an HTTP 409 response with a message explaining the deletion is reversible by re-running the bootstrap command (`anvil bootstrap-datasets`). Users may force-delete by sending `force: true` in the request body. After deletion, the dataset name is freed and re-running the bootstrap will re-import it.

### Key Entities

- **Corpus (primary)**: A collection of files from a directory ingested via the existing corpus pipeline. Demo corpora are directories under `data/demo/` containing text files organized by size/name.
- **Dataset (secondary)**: A collection of text samples stored in the database. A small number of demo `.txt` uploads are also provided as a secondary demonstration path.
- **Demo Data Source**: A physical directory or file under `data/demo/` organized as `data/demo/<size>/<name>/` with subdirectories serving as corpora and standalone `.txt` files as datasets.

## Success Criteria

### Measurable Outcomes

- **SC-001**: A fresh clone of the repo can train a model to completion without any external network access, using only bundled demo data
- **SC-002**: At least 3 distinct corpora (size × domain combinations) are available for selection in the UI and CLI after running the bootstrap step, demonstrating corpus ingestion as the primary path
- **SC-003**: After removing the hardcoded external download fallback, all existing tests pass without modification (the fallback code paths are only exercised when no dataset/corpus is specified)
- **SC-004**: Total demo data in the repository is under 500 KB
- **SC-005**: The bootstrap import process completes in under 5 seconds on modern hardware
- **SC-006**: At least one `.txt` file is available as a secondary demo dataset (upload path), showing both corpus and dataset workflows

## Assumptions

- Demo data will be organized as directories of text files under `data/demo/` (corpus format) as the primary path, with some standalone `.txt` files for the dataset upload demo path
- The existing corpus ingestion pipeline (`CorpusService` + `CorpusLoader`) will be reused to ingest demo corpora into the database
- A small number of `.txt` dataset uploads will demonstrate the dataset import path, but corpus ingestion is the primary pattern
- Demo datasets/corpora are deletable with a warning (FR-009); re-bootstrap recreates them since the name is now free
- Users who already specify `corpus_id` or `dataset_id` explicitly are unaffected by the removal of the external download fallback
- The CLI `train` command and the API training endpoint will use the same default demo dataset detection logic
- The hardcoded `DEMO_CORPUS` in the inference service (`anvil/services/inference.py`) is also in scope — the demo model pre-trained at startup should use one of the curated demo datasets instead of its own hardcoded inline corpus