# Feature Specification: Add from __future__ import annotations to Schema Files

**Feature Branch**: `opencode/witty-forest`  
**Created**: 2026-07-18  
**Status**: Draft  
**Priority**: P2  
**Input**: Codebase review finding #078 — `schemas_dataset.py`, `inference_schemas.py`, and `schemas_eval.py` (and potentially other schema files) lack `from __future__ import annotations` (PEP 563), which is used consistently throughout the rest of the codebase per the project's coding standards.

## User Scenarios & Testing

### User Story 1 - Consistent PEP 563 usage (Priority: P2)

All Python files in the `anvil/` package use `from __future__ import annotations` as the first import (or second after the copyright header) to enable deferred annotation evaluation.

**Why this priority**: The codebase standard (per AGENTS.md Principle 10) mandates PEP 563 for all files. Inconsistent usage creates forward-reference issues when models reference types defined later or in other modules. Without deferred annotations, string literals are required for forward refs.

**Independent Test**: A grep for `from __future__ import annotations` across all `anvil/api/v1/schemas_*.py` files shows it present in every file.

**Acceptance Scenarios**:

1. **Given** any file in `anvil/api/v1/schemas_*.py`, **When** inspected, **Then** it has `from __future__ import annotations` as the first code import.
2. **Given** the files are type-checked with mypy, **When** they reference forward types, **Then** no quoting is needed for those types.

---

### User Story 2 - No string-literal forward references (Priority: P2)

Pydantic model fields and method signatures use bare type names instead of quoted string literals (`"MyClass"` vs `MyClass`).

**Why this priority**: String-literal forward references are error-prone and inconsistent with the codebase standard. PEP 563 makes them unnecessary.

**Independent Test**: grep for `"` in type annotation positions in schema files shows zero string-literal forward references.

**Acceptance Scenarios**:

1. **Given** a Pydantic model that references another model type, **When** inspected, **Then** the reference is a bare name (not a quoted string).
2. **Given** mypy type-checks the file, **When** it encounters a forward reference, **Then** it resolves correctly without quoting.

### Edge Cases

- Files that also need `TYPE_CHECKING` imports for cycle-breaking must add the annotation import first, then the guarded import.
- The `# one-class:allow` comment on `schemas_misc.py` and `schemas_dataset.py` must be preserved.

## Requirements

### Functional Requirements

- **FR-001**: `from __future__ import annotations` MUST be added to `anvil/api/v1/schemas_dataset.py` (currently missing).
- **FR-002**: `from __future__ import annotations` MUST be added to `anvil/api/v1/inference_schemas.py` (currently missing).
- **FR-003**: `from __future__ import annotations` MUST be added to `anvil/api/v1/schemas_eval.py` (currently missing).
- **FR-004**: All other `anvil/api/v1/schemas_*.py` files MUST be audited and the import added if missing.
- **FR-005**: No string-literal forward references ("MyClass") in any schema file.
- **FR-006**: A lint check SHOULD be added to enforce this (e.g., add to `make lint` or extend the existing `check_import_placement.py`).
- **FR-007**: `from __future__ import annotations` MUST be placed as the first import after the copyright header, before any other imports.
- **FR-008**: `mypy --strict` must pass with zero new errors.

### Key Entities

- **schemas_dataset.py**: Currently missing PEP 563
- **inference_schemas.py**: Currently missing PEP 563
- **schemas_eval.py**: Currently missing PEP 563
- **schemas_misc.py**: Already has it (verify)
- **schemas_content.py**: Already has it (verify)

## Success Criteria

### Measurable Outcomes

- **SC-001**: Every `anvil/api/v1/schemas_*.py` file has `from __future__ import annotations`.
- **SC-002**: Zero string-literal forward references in schema files.
- **SC-003**: `make lint` and `make typecheck` pass.
- **SC-004**: No behavioral changes — Pydantic models serialize identically.

## Assumptions

- No existing behavior changes — PEP 563 is a semantic change (all annotations become strings) but Pydantic v2 handles this correctly via `get_type_hints()`.
- Files that already have the import do not need modification.
