# Feature Specification: Add extra="forbid" to Schema Files

**Feature Branch**: `opencode/witty-forest`  
**Created**: 2026-07-18  
**Status**: Draft  
**Priority**: P1  
**Input**: Codebase review finding #073 — `schemas_content.py` (12 models) and `schemas_dataset.py` (8 models) lack `ConfigDict(extra="forbid")`, allowing unknown fields in API request bodies to be silently accepted instead of rejected.

## User Scenarios & Testing

### User Story 1 - Strict request body validation (Priority: P1)

All API request bodies reject unknown fields at the Pydantic validation layer, preventing typos in client code from going unnoticed.

**Why this priority**: Silent field acceptance masks client bugs. If a client sends `"namme": "foo"` instead of `"name": "foo"`, the typo is silently ignored and the server operates with a default or missing value. `extra="forbid"` catches this at the API boundary.

**Independent Test**: Sending a POST with an extra unknown field returns 422 instead of 200.

**Acceptance Scenarios**:

1. **Given** `POST /v1/datasets` with payload `{"name": "test", "extra_field": "should_fail"}`, **When** the request is processed, **Then** the response is 422 with a validation error mentioning `extra_field`.
2. **Given** any existing valid request body for a dataset endpoint, **When** sent without extra fields, **Then** it succeeds as before.

---

### User Story 2 - Consistent validation across all schemas (Priority: P2)

Every Pydantic model used as a request body throughout the codebase has `ConfigDict(extra="forbid")`.

**Why this priority**: Inconsistency creates unpredictable API behavior — some endpoints are strict, others are lenient. A developer modifying a schema file must remember to add `extra="forbid"` each time.

**Independent Test**: A linter or audit can verify that every Pydantic model has a `model_config` with `extra="forbid"`.

**Acceptance Scenarios**:

1. **Given** any file in `anvil/api/v1/schemas_*.py`, **When** inspected, **Then** every `BaseModel` subclass has `model_config = ConfigDict(extra="forbid")`.
2. **Given** any service-layer Pydantic model used as an API input, **When** inspected, **Then** it also has `extra="forbid"`.

### Edge Cases

- Models used for both input and output should have different configs for each role (split them).
- Models that intentionally accept extra fields (e.g., raw metadata passthrough) should have a comment explaining why.

## Requirements

### Functional Requirements

- **FR-001**: All models in `anvil/api/v1/schemas_content.py` (12 models) MUST be updated with `model_config = ConfigDict(extra="forbid")`.
- **FR-002**: All models in `anvil/api/v1/schemas_dataset.py` (8 models) MUST be updated with `model_config = ConfigDict(extra="forbid")`.
- **FR-003**: A script or audit check SHOULD be created to verify all API input models have `extra="forbid"` (e.g., add to `make vault-audit` or `make lint`).
- **FR-004**: Models that serve dual input/output roles MUST be split into separate input and output models (input gets `extra="forbid"`, output gets `extra="ignore"` or `extra="allow"`).
- **FR-005**: All existing tests MUST pass unchanged — request bodies in tests do not include extra fields.

### Key Entities

- **schemas_content.py**: 12 models needing `extra="forbid"` — `ContentCorpusCreate`, `SessionOpenBody`, `FreezeVersionBody`, `LockBody`, `RevertBody`, `ImportStart`, `ImportJobOut`, etc.
- **schemas_dataset.py**: 8 models needing `extra="forbid"` — `CreateDatasetBody`, `ImportBody`, `FilterBody`, `ReplaceBody`, `UpdateSampleBody`, `CloneDatasetBody`, `CreateFromCorpusBody`, `UpdateDatasetBody`

## Success Criteria

### Measurable Outcomes

- **SC-001**: Zero Pydantic request-body models in `anvil/api/v1/` lack `extra="forbid"`.
- **SC-002**: Sending an unknown field to any endpoint returns HTTP 422.
- **SC-003**: `make test` passes with zero regressions.
- **SC-004**: No changes needed to existing valid requests in tests.

## Assumptions

- All models in the identified files are request-body models (some may also be response models — those need separation).
- Adding `extra="forbid"` does not break any existing client that was accidentally relying on silent field acceptance.
