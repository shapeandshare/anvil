# Quickstart: Responsible Sample Data & Universal No-Harm Governance

**Feature**: `010-responsible-data-governance`

This guide validates the feature end-to-end after implementation. Follow the project's standard flow (`make setup` → `make run`) and the quality gates (`make lint`, `make typecheck`, `make test` at 100% coverage).

## Prerequisites
- `make setup` completed; fresh DB (`rm -f data/anvil-state.db` for a clean first-run, optional).

## 1. Bundled provenance is seeded (User Story 1)
```bash
make run            # first run seeds demo data + license catalog
curl -s localhost:8080/v1/datasets | jq '.data[] | {name, provenance}'
```
**Expect**: every demo dataset/corpus shows `provenance` with non-empty `source`, an approved `license` (e.g. `Public Domain`, `MIT`, `Generated/Original`), and `origin: "bundled"`.

```bash
curl -s localhost:8080/v1/governance/licenses | jq '.data[].identifier'
```
**Expect**: the broad approved set (Public Domain, CC0-1.0, MIT, BSD-2/3-Clause, Apache-2.0, CC-BY-4.0, CC-BY-SA-4.0, Generated/Original) plus the `own-content` sentinel.

**Negative**: remove an entry from `anvil/data/demo/provenance.json`, wipe DB, `make run` again → that item is NOT seeded and the refusal appears in the audit trail (step 4).

## 2. Acceptable-use gate on upload (User Story 3)
```bash
# Reject: missing affirmation
curl -s -X POST localhost:8080/v1/datasets/upload \
  -F file=@sample.txt -F declared_source="my notes" -F license="own-content" -F acceptable_use_affirmed=false
```
**Expect**: HTTP 422, `{"data": null, "error": "<clear reason about missing acceptable-use affirmation>"}`.

```bash
# Accept: own-content, compliant
curl -s -X POST localhost:8080/v1/datasets/upload \
  -F file=@sample.txt -F declared_source="my notes" -F license="own-content" -F acceptable_use_affirmed=true
```
**Expect**: 200/201, dataset created with `provenance.origin="user"`, `license="own-content"`.

## 3. Deletion removes artifacts (User Story 4 / SC-005)
```bash
ID=<id from step 2>
curl -s -X DELETE localhost:8080/v1/datasets/$ID
ls data/datasets/$ID 2>/dev/null && echo "ORPHANS!" || echo "clean (zero orphans)"
```
**Expect**: `clean (zero orphans)`.

## 4. Audit trail & tamper-evidence (User Story 2 / SC-009)
```bash
curl -s localhost:8080/v1/governance/audit | jq '.data[] | {sequence, action_type, target_type, outcome, reason}'
```
**Expect**: chronological entries for `seed`, `upload`, `policy_accept`, `policy_reject`, `delete` (and any refusals from step 1's negative case).

```bash
curl -s localhost:8080/v1/governance/audit/verify | jq
```
**Expect**: `{"valid": true, "break_at_sequence": null, ...}`.

**Tamper test (manual)**: directly edit one `audit_events` row in SQLite, re-run verify → `{"valid": false, "break_at_sequence": <K>}`.

## 5. Policy page (SC-006)
```bash
open http://localhost:8080/v1/acceptable-use
```
**Expect**: a polished (design-token) page stating the universal no-harm stance applies to bundled data, user data, and system usage; linked from nav and the upload form.

## 6. Quality gates (Constitution Articles IV, plus strict typing)
```bash
make lint && make typecheck && make test
```
**Expect**: lint clean, `mypy --strict` clean (no suppressions), tests pass at 100% coverage including new contract/unit/integration suites.

## 7. Migration reversibility
```bash
# downgrade/upgrade round-trip leaves schema consistent
make db-downgrade && make db-upgrade   # or equivalent alembic targets
```
**Expect**: clean round-trip; provenance columns + `audit_events` + `license_catalog` created on upgrade, dropped on downgrade.

---

### Success mapping
| Step | Validates |
|---|---|
| 1 | FR-001..FR-006, SC-001, SC-002 (US1) |
| 2 | FR-014..FR-017, SC-004, SC-008 (US3) |
| 3 | FR-021, SC-005 (US4) |
| 4 | FR-008..FR-013, FR-023, SC-003, SC-009 (US2) |
| 5 | FR-017..FR-019, SC-006 (US4) |
| 6–7 | Constitution gates (TDD, strict typing, reversible migration) |
