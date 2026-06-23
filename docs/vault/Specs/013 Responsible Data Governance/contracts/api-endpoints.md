# Contract: HTTP API Endpoints

All responses use the existing wrapper `{"data": <payload> | null, "error": <message> | null}`. Routes are async and obtain all DB-backed services through the **`AnvilWorkbench` God Class** via `workbench: AnvilWorkbench = Depends(get_workbench)` (Article VII — no inline service/repository construction). Routes are registered via `anvil/api/v1/router.py`.

---

## Modified: `POST /v1/datasets/upload`  (acceptable-use gate)

**Request** (multipart): `file: UploadFile` + form fields `declared_source: str`, `license: str`, `acceptable_use_affirmed: bool`.

**Behavior**:
- Calls `GovernanceService.evaluate_submission(...)` BEFORE creating the dataset.
- **Reject** (gate fails): HTTP `422`, body `{"data": null, "error": "<clear respectful reason>"}`. A `policy_reject` audit event is recorded. No dataset created.
- **Accept**: creates `Dataset`, assigns provenance (`origin="user"`, `license_id`, attribution), records `upload` + `policy_accept` audit events, returns `201`/`200` with `{"data": {<dataset>, "provenance": {...}}, "error": null}`.

**Contract tests**: missing each gate field → 422 + audit reject; compliant → dataset persisted + provenance + audit accept.

---

## Modified: `POST /v1/datasets/{id}/import`  (acceptable-use gate)

**Request body** (`ImportBody` extended): `format`, `text`, `declared_source`, `license`, `acceptable_use_affirmed`.

**Behavior**: same gate as upload; on accept proceeds to existing `DatasetImportService.commit_import`, records `import` + `policy_accept`; on reject 422 + `policy_reject`, no samples written.

---

## Modified: `DELETE /v1/datasets/{id}`  (artifact cleanup + audit)

**Query**: `force: bool = false` (preserves demo-protection guard).

**Behavior**:
- Existing guards retained (404 not found; 409 for `"Demo - "` without `force`; 409 for referencing training configs).
- On delete: removes all `Sample` artifacts via `LocalFileStore.delete(...)` AND sweeps the `{dataset_id}/` directory (SC-005 zero orphans), deletes DB rows, records a `delete` audit event.
- Returns `{"data": {"message": "Dataset deleted"}, "error": null}`.

**Contract test**: after delete, no files remain under `data/datasets/{id}/`; audit `delete` event present.

---

## New: `GET /v1/governance/audit`  (audit query — FR-012)

**Query**: `target_type?`, `target_id?`, `action_type?`, `limit=200`, `offset=0`.
**Response**: `{"data": [AuditEventOut...], "error": null}` ordered by `sequence` asc.

## New: `GET /v1/governance/audit/verify`  (integrity — SC-009)

**Response**: `{"data": {"valid": bool, "break_at_sequence": int | null, "entries_checked": int}, "error": null}`.

## New: `GET /v1/governance/licenses`  (catalog for UI select — FR-005)

**Response**: `{"data": [{"identifier", "display_name", "requires_attribution", "is_own_content_sentinel"}...], "error": null}`.

## New: `GET /v1/governance/datasets/{id}/report`  (per-dataset provenance + audit report — SC-007)

Composes `workbench.governance.get_provenance(target_type=DATASET, target_id=id)` with `workbench.audit.list_events(target_type=DATASET, target_id=id)`.
**Response**: `{"data": {"provenance": ProvenanceOut, "audit": [AuditEventOut...]}, "error": null}` — provenance plus the dataset's complete chronological audit history in a single response (satisfies SC-007's "one response" verifiability).

## New: `POST /v1/datasets/{id}/takedown`  (FR-020/FR-021)

**Body** (`TakedownBody`): `reason: str`.
**Behavior**: delegates to `GovernanceService.takedown`; removes record + artifacts (zero orphans), records `takedown` audit event. `409` if blocked by guards without `force`.

## New page: `GET /v1/acceptable-use`  (policy page — FR-017/FR-019/SC-006)

**Response**: `HTMLResponse` rendering `acceptable_use.html` (server-side). Linked from nav and from the data-entry surface. States the universal no-harm stance applies to bundled data, user data, and system usage (FR-018).

## Modified: `GET /v1/datasets`  &  `GET /v1/datasets-page`  (provenance surfacing — FR-005)

- `GET /v1/datasets` (and `/v1/corpora`) responses include a `provenance` object (`source`, `license`, `attribution`, `origin`) per item.
- `GET /v1/datasets-page` `TemplateResponse` passes the license-catalog list as context for the upload-form select; template displays per-row provenance and the upload-gate fields using design tokens.
