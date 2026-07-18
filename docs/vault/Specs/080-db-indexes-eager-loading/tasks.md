# Tasks — 080 FK Indexes and N+1 Prevention

**TDD order. ⚠️ Resolve the external_models FK inconsistency FIRST (see context.md).**

## Phase 0 — Investigate (CRITICAL)
- [ ] T001 Read `013_drop_external_models.py` — determine if `external_models` table actually still exists.
- [ ] T002 Resolve the dangling FK question for `fine_tune_datasets.external_model_id` and `lora_adapters.external_model_id`. If truly dropped → escalate as a separate data-model bug; EXCLUDE those two indexes from this spec.
- [ ] T003 Verify `license_id` columns exist on `datasets`, `corpora`, `content_corpora`.
- [ ] T004 Confirm next migration number is `015`.

## Phase 1 — Add indexes (Red-Green)
- [ ] T010 **[Red]** Write a test (or `EXPLAIN QUERY PLAN` check) asserting an index is used for `fine_tune_datasets.dataset_id` filtering. Confirm FAILS (full scan).
- [ ] T011 **[Green]** Add `index=True` to the safe FK `mapped_column`s (dataset_id, chat_template_id, license_id×3). Create migration `015_add_fk_indexes.py` with explicit index names.
- [ ] T012 Run migration; confirm indexes created.

## Phase 2 — N+1 audit & eager loading
- [ ] T020 Audit relationship-in-loop access (context.md grep). Identify concrete N+1 sites.
- [ ] T021 **[Red]** For an identified site, write a test asserting query count (e.g. 2, not N+1) using SQL logging/event counting.
- [ ] T022 **[Green]** Add `selectinload()` to the relevant repository query. Make the query-count test pass.

## Phase 3 — Gates
- [ ] T030 `make test` — migration applies cleanly, no data breakage.
- [ ] T031 `make lint && make typecheck && make vault-audit`.

## Verification (Success Criteria)
- SC-001: migration 015 adds all SAFE FK indexes (external_model_id excluded if dangling).
- SC-002: query count for audited relationship access is verified (no N+1).
- SC-003: gates green.
- SC-004: no regressions (indexes additive).

## Escalation Note
If T002 confirms `external_models` is dropped but FKs remain, file this as a separate data-model bug — it is out of scope for a pure "add indexes" spec and needs a dedicated fix (repoint FKs to `catalog_identities` or remove them).
