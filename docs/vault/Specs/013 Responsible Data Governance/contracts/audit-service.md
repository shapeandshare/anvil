# Contract: AuditService

**Module**: `anvil/services/governance/audit_service.py` | **Layer**: Service (consumes `AuditEventRepository`)

> Result/value types referenced below (`ChainVerifyResult`) are Pydantic `BaseModel`s co-located one-per-file in `anvil/services/governance/` (ADR-019/020). StrEnums (`AuditAction`, `AuditTargetType`, `AuditOutcome`) likewise live in that package; method params/columns use the enums, not raw strings.
> **Exposed through the `AnvilWorkbench` God Class** as `workbench.audit` (Article VII); callers obtain it via the `get_workbench` dependency. The repository it consumes is bound to the caller's request session so audit writes share the action's transaction (FR-011).

Async service implementing the hash-chained, append-only, indefinitely-retained audit trail (FR-008–FR-013, FR-023). Mirrors the `DatasetService` constructor/async convention. **Must NOT** mimic `TrackingService` fire-and-forget behavior — audit-write failure is raised, not swallowed (FR-011).

## Constructor

```python
class AuditService:
    def __init__(self, repo: AuditEventRepository) -> None: ...
```

## Methods

### `record`
```python
async def record(
    self,
    *,
    action_type: str,      # seed|upload|import|curate|delete|takedown|policy_accept|policy_reject|chain_checkpoint
    target_type: str,      # dataset|corpus|sample|policy|audit_chain
    target_id: str | None,
    actor: str,            # e.g. "system:bootstrap", "user:session"
    outcome: str,          # success|rejected|error
    reason: str | None = None,
    params: dict[str, object] | None = None,
    event_timestamp: datetime | None = None,  # defaults to now (UTC)
) -> AuditEvent:
```
- **Contract**:
  - C-A1: Reads current chain tail (`prev_hash`) and appends within the SAME session/transaction as the caller's action (caller passes the repo bound to the action's session).
  - C-A2: Computes `entry_hash` per the canonical-JSON sha256 definition in data-model.md.
  - C-A3: Assigns `sequence = previous.sequence + 1` (genesis `sequence=1`, `prev_hash`=64 zeros).
  - C-A4: On any failure to persist, raises (caller's transaction rolls back). Never returns silently on failure.
  - C-A5: `params` MUST NOT contain full content bodies — references/summaries only (FR-013). Service is responsible for stripping/normalizing.

### `verify_chain`
```python
async def verify_chain(self) -> ChainVerifyResult:  # {valid: bool, break_at_sequence: int | None, entries_checked: int}
```
- **Contract**:
  - C-A6: Returns `valid=True` for an untouched chain; `valid=False` with the first broken `break_at_sequence` for any tampered/inserted/removed entry (SC-009).
  - C-A7: Read-only; performs no writes.

### `list_events`
```python
async def list_events(
    self,
    *,
    target_type: str | None = None,
    target_id: str | None = None,
    action_type: str | None = None,
    limit: int = 200,
    offset: int = 0,
) -> Sequence[AuditEvent]:
```
- **Contract**: C-A8: Returns entries in chronological (`sequence` ascending) order, filterable (FR-012).

### `checkpoint`
```python
async def checkpoint(self, *, actor: str, reason: str) -> AuditEvent:
```
- **Contract**: C-A9: Appends a `chain_checkpoint` event (the only sanctioned way to mark archival/reset — FR-023). Does not delete prior entries.

## Repository contract — `AuditEventRepository` (`anvil/db/repositories/audit_events.py`)

```python
class AuditEventRepository:
    def __init__(self, session: AsyncSession) -> None: ...
    async def get_tail(self) -> AuditEvent | None: ...           # highest sequence
    async def append(self, event: AuditEvent) -> AuditEvent: ...  # add + flush + refresh
    async def all_ordered(self) -> Sequence[AuditEvent]: ...      # sequence asc (for verify)
    async def query(self, **filters) -> Sequence[AuditEvent]: ... # filtered, sequence asc
    # NO update / NO delete methods exposed (append-only invariant, VR-A3)
```

## Test obligations (TDD)
- T-A1 (unit): genesis entry has `sequence=1`, `prev_hash`=64 zeros, recomputed hash matches.
- T-A2 (unit): N-th entry `prev_hash == (N-1).entry_hash`.
- T-A3 (unit): `verify_chain` returns valid for clean chain.
- T-A4 (unit): mutating any field of entry K makes `verify_chain` return `valid=False, break_at_sequence=K`.
- T-A5 (unit): removing entry K detected; inserting a forged entry detected.
- T-A6 (integration): a forced repository failure during `record` rolls back the caller's action and raises (FR-011).
- T-A7 (unit): `list_events` ordering + filters.
