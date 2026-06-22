# Contract: GovernanceService

**Module**: `anvil/services/governance/governance_service.py` | **Layer**: Service (consumes `LicenseRepository`, provenance via `DatasetRepository`/`CorpusRepository`, and `AuditService`)

> Co-located in the `anvil/services/governance/` domain sub-package (Article X): `license_seed.py`, result/value types (`GateDecision`, `ProvenanceView` as Pydantic `BaseModel`), and the `DataOrigin` StrEnum. Catalog seed set per Clarification Q4.
> **Exposed through the `AnvilWorkbench` God Class** as `workbench.governance` (Article VII); routes/CLI/tests access it via the `get_workbench` dependency, never by direct construction.

Implements the acceptable-use gate, approved-license catalog access, provenance assignment/lookup, and takedown (FR-002, FR-003, FR-005–FR-007, FR-014–FR-022). Affirmation/declaration-based only — **no content scanning** (Clarification Q3).

## Constructor

```python
class GovernanceService:
    def __init__(
        self,
        license_repo: LicenseRepository,
        audit: AuditService,
    ) -> None: ...
```

## License catalog

### `list_licenses`
```python
async def list_licenses(self, *, include_own_content: bool = True) -> Sequence[LicenseEntry]: ...
```
- C-G1: Returns the approved-license catalog (for UI select + validation). `own-content` sentinel included when `include_own_content`.

### `seed_catalog`
```python
async def seed_catalog(self) -> int:  # number of newly inserted licenses
```
- C-G2: Idempotent seed from `anvil/services/governance/license_seed.py` (Clarification Q4 set). Skips existing identifiers.

## Acceptable-use gate

### `evaluate_submission`
```python
async def evaluate_submission(
    self,
    *,
    declared_source: str,
    license_identifier: str,
    acceptable_use_affirmed: bool,
    is_empty_or_unparseable: bool,
    actor: str,
    target_type: str,             # dataset | corpus
    target_id: str | None,
) -> GateDecision:                # {accepted: bool, reason: str | None, license_id: int | None, origin: str}
```
- **Contract**:
  - C-G3 (FR-014/FR-015): rejects (`accepted=False`) when `declared_source` empty, `license_identifier` is neither an approved license nor `own-content`, `acceptable_use_affirmed` is False, or `is_empty_or_unparseable` is True. Returns a clear, respectful `reason` (SC-008).
  - C-G4 (Clarification Q1): `own-content` identifier is accepted for user submissions without appearing on the approved-redistribution list; `origin="user"`.
  - C-G5 (FR-016): records a `policy_accept` or `policy_reject` audit event with `reason` for EVERY evaluation (via `AuditService.record`).
  - C-G6: performs NO content inspection (no keyword/PII/ML) — decision is purely declaration-based.

## Provenance

### `assign_provenance` / `get_provenance`
```python
async def assign_provenance(
    self, *, entity, source_description: str, license_id: int,
    attribution_text: str | None, origin: str, parent_provenance_ref: int | None = None,
) -> None: ...
async def get_provenance(self, *, target_type: str, target_id: int) -> ProvenanceView: ...
```
- C-G7 (FR-006/VR-P3): if license `requires_attribution`, `attribution_text` MUST be non-empty else raise `ValueError`.
- C-G8 (FR-007): `carry_forward_provenance(parent, child)` copies parent provenance and sets `child.parent_provenance_ref = parent.id`.

### `validate_bundled`
```python
async def validate_bundled(self, *, source_description: str, license_identifier: str) -> tuple[bool, str | None]: ...
```
- C-G9 (FR-003/VR-P1): returns `(False, reason)` when a bundled sample's license is missing/empty/not on the approved list (and is NOT the own-content sentinel). Caller skips seeding and records the refusal.

## Takedown

### `takedown`
```python
async def takedown(self, *, target_type: str, target_id: int, reason: str, actor: str, dataset_service) -> None: ...
```
- C-G10 (FR-020/FR-021/SC-005): removes the entity record AND all associated stored artifacts (delegates artifact removal to `DatasetService.delete_dataset` artifact-cleanup path), leaving zero orphans, then records a `takedown` audit event.
- C-G11 (FR-022): preserves the demo-protection guard (bundled data requires explicit override).

## Test obligations (TDD)
- T-G1: gate rejects each missing field independently with a clear reason; accepts a fully compliant submission.
- T-G2: `own-content` accepted for user data without approved-license membership.
- T-G3: every gate decision produces exactly one `policy_accept`/`policy_reject` audit event.
- T-G4: attribution-required license with empty attribution raises.
- T-G5: `validate_bundled` rejects unknown/empty license for bundled origin.
- T-G6: takedown removes DB row + artifacts (zero orphans) + audit event.
- T-G7: provenance carry-forward on clone/fork copies fields and sets parent ref.
