# Feature Specification: FK Indexes and N+1 Query Prevention

**Feature Branch**: `opencode/witty-forest`  
**Created**: 2026-07-18  
**Status**: Draft  
**Priority**: P2  
**Input**: Codebase review finding #080b — Multiple foreign key columns lack indexes (`FineTuneDataset.dataset_id`, `FineTuneDataset.chat_template_id`, `LoRAAdapter.external_model_id`, license_id FKs). No `selectinload()` or `joinedload()` eager loading is used in any repository, creating N+1 risk when services access relationship attributes in loops.

## User Scenarios & Testing

### User Story 1 - FK columns are indexed (Priority: P2)

All foreign key columns used in `WHERE`, `JOIN`, or filter conditions have database indexes defined on them.

**Why this priority**: In SQLite (and all databases), FK columns do not automatically get indexes. Queries that filter or join on unindexed FK columns perform full table scans. As data grows (1000s of fine-tune datasets, adapters, etc.), this becomes a performance bottleneck.

**Independent Test**: `EXPLAIN QUERY PLAN` for a query filtering on `FineTuneDataset.dataset_id` shows an index lookup instead of a full table scan.

**Acceptance Scenarios**:

1. **Given** the `fine_tune_datasets` table, **When** a query filters on `dataset_id`, **Then** an index `ix_fine_tune_datasets_dataset_id` is used.
2. **Given** the `fine_tune_datasets` table, **When** a query filters on `chat_template_id`, **Then** an index `ix_fine_tune_datasets_chat_template_id` is used.
3. **Given** the `lora_adapters` table, **When** a query filters on `external_model_id`, **Then** an index `ix_lora_adapters_external_model_id` is used.
4. **Given** the `datasets`, `corpora`, and `content_corpora` tables, **When** a query filters on `license_id`, **Then** an index for that FK column is used.

---

### User Story 2 - Eager loading prevents N+1 (Priority: P2)

Service code that accesses ORM relationships in loops uses `selectinload()` or `joinedload()` on the initial query to avoid N+1 queries.

**Why this priority**: Without eager loading, accessing `corpus.files` in a loop triggers a separate SQL query per iteration. With 1000 corpora, that's 1 + 1000 = 1001 queries instead of 2.

**Independent Test**: Adding eager loading to a repository query and verifying via SQL logging that only 2 queries execute (1 for entities, 1 for related entities).

**Acceptance Scenarios**:

1. **Given** a repository method that returns entities with relationships, **When** the service layer accesses those relationships in a loop, **Then** the repository uses `selectinload()` to pre-fetch them.
2. **Given** an Alembic migration adds the new FK indexes, **When** it runs, **Then** it does not break existing data or queries.

### Edge Cases

- SQLite has a limit of 64 joins — `joinedload()` with many joins could hit this. `selectinload()` is preferred for to-many relationships.
- Adding indexes to large tables with existing data may take time during migration. Acceptable for the initial migration.
- Indexes add write overhead — benchmark tradeoff is acceptable for query-heavy tables.

## Requirements

### Functional Requirements

- **FR-001**: An Alembic migration MUST add indexes on the following FK columns:
  - `fine_tune_datasets.dataset_id` → `ix_fine_tune_datasets_dataset_id`
  - `fine_tune_datasets.chat_template_id` → `ix_fine_tune_datasets_chat_template_id`
  - `lora_adapters.external_model_id` → `ix_lora_adapters_external_model_id`
  - `datasets.license_id` → `ix_datasets_license_id`
  - `corpora.license_id` → `ix_corpora_license_id`
  - `content_corpora.license_id` → `ix_content_corpora_license_id`
- **FR-002**: An audit of service layer relationship access patterns MUST be performed to identify N+1 risks.
- **FR-003**: Repository methods that return entities whose relationships are accessed in loops MUST use `selectinload()` (preferred) or `joinedload()`.
- **FR-004**: The audit and eager loading fixes MUST be done in the same PR as the index migration (or a follow-up).
- **FR-005**: `make test` must pass after migration and code changes.

### Key Entities

- **fine_tune_datasets table**: FK columns `dataset_id`, `chat_template_id`
- **lora_adapters table**: FK column `external_model_id`
- **datasets table**: FK column `license_id`
- **corpora table**: FK column `license_id`
- **content_corpora table**: FK column `license_id`
- **Repository methods**: Methods like `corpus_repo.get_all()`, `dataset_repo.get_all()` that may trigger N+1
- **Alembic migration**: New migration (015) adding indexes

## Success Criteria

### Measurable Outcomes

- **SC-001**: New Alembic migration adds all 6+ FK indexes.
- **SC-002**: SQL query count for common relationship-access patterns is verified (e.g., `corpora -> files` produces 2 queries, not N+1).
- **SC-003**: `make test` and `make typecheck` pass.
- **SC-004**: No regressions in existing tests (indexes are additive, not breaking).

## Assumptions

- Adding indexes to small-tables (fine_tune_datasets may have few rows) is still beneficial — the index overhead is minimal for SQLite.
- The N+1 audit is done by searching for patterns like `for x in entities: x.relationship` and checking if eager loading is present.
- Alembic autogenerate can detect the new index definitions and create the migration.
