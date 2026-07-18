# Context — 073 Add extra="forbid" to Schema Files

> Cross-references: `../066-codebase-remediation/data-inventory.md` §6.

## Current State (verified)

`grep -c 'extra="forbid"'` on both files → **0 matches**.

**`schemas_content.py`** (15 models, line refs):
- Request bodies (need `extra="forbid"`): `ContentCorpusCreate` (22), `SessionOpenBody` (138), `CompositionSpecItem` (222), `FreezeVersionBody` (237), `TagBody` (257), `LockBody` (269), `RevertBody` (311), `ImportStart` (323).
- Response models (`*Out` — leave default or `extra="ignore"`): `ContentCorpusOut` (60), `ContentVersionOut` (102), `SessionOut` (153), `AcceptOut` (183), `ValidationReportOut` (207), `LockOut` (284), `ImportJobOut` (341).

**`schemas_dataset.py`** (8 models, ALL request bodies): `CreateDatasetBody` (18), `UpdateDatasetBody` (33), `ImportBody` (48), `FilterBody` (63), `ReplaceBody` (78), `UpdateSampleBody` (96), `CloneDatasetBody` (108), `CreateFromCorpusBody` (123).

Re-verify: `grep -c 'extra="forbid"' anvil/api/v1/schemas_content.py anvil/api/v1/schemas_dataset.py`

## Reference Pattern

`schemas_misc.py` already does it right:
```python
class RegisterModelBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    experiment_id: int
```

## Scope Extension

The original review named only these 2 files, but OTHER schema files may also lack `extra="forbid"` on request bodies. Audit ALL `schemas_*.py`:
```bash
for f in anvil/api/v1/schemas_*.py; do echo "$f: $(grep -c 'extra="forbid"' $f) forbid / $(grep -c 'class.*BaseModel' $f) models"; done
```

## Gotchas

- Only REQUEST bodies get `extra="forbid"`. Response models (`*Out`) should NOT forbid extras (they're outbound; use default or `extra="ignore"`).
- Distinguish request vs response by naming: `*Body`/`*Create`/`*In`/`*Start`/`*Item` = request; `*Out`/`*Response` = response.
- Tests must not send extra fields — check existing tests still pass (they shouldn't include extras).
- This is the smallest, lowest-risk spec — good warmup/first PR.
