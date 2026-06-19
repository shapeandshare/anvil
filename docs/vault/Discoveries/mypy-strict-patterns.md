---
title: Mypy Strict Enforcement Patterns
type: discovery
tags:
  - type/discovery
  - domain/architecture
  - domain/governance
  - status/reviewed
created: '2026-06-19'
updated: '2026-06-19'
aliases:
  - Mypy Strict Enforcement Patterns
  - mypy-strict-patterns
source: agent
code-refs:
  - anvil/db/migration.py
  - anvil/services/compute/modal_backend.py
  - anvil/core/torch_engine.py
  - anvil/services/inference.py
  - pyproject.toml
---
# Mypy Strict Enforcement Patterns

During the mypy `--strict` enforcement sweep, several boundary patterns were identified where `Any` is the **correct** annotation — not abuse. These patterns should not be "fixed" by future enforcement sweeps.

## Legitimate `Any` Boundaries

### 1. Sync-to-Async Forwarding Wrapper (`_run_sync`)

**Location**: `anvil/db/migration.py::MigrationService._run_sync`

```python
async def _run_sync(self, fn, *args: Any, **kwargs: Any) -> Any:
```

This is a private wrapper that dispatches synchronous Alembic commands into a thread executor. The `fn` parameter is deliberately untyped (it accepts any Alembic command function), and `*args: Any, **kwargs: Any` correctly models the forwarding interface. The return `-> Any` is correct because the return type depends on which Alembic command is called.

Not fixable with `ParamSpec` due to mypy limitations with nested closures at the call sites (the inner `_create` closures lose type info through the `ParamSpec` inference boundary).

### 2. External Library Boundary (`_build_remote_function`)

**Location**: `anvil/services/compute/modal_backend.py::ModalBackend._build_remote_function`

```python
@staticmethod
def _build_remote_function(modal_module: Any) -> Any:
```

The `modal` package is an external library without type stubs. The `modal_module` parameter receives the imported `modal` module object, and the return is a Modal FunctionHandle (a Modal-specific type). Both are opaque external types. Using `ModuleType` for the parameter causes `modal_module.App` type errors, and the return type has no stubbable equivalent.

### 3. Optional Import Pattern

**Location**: `anvil/core/torch_engine.py`

The canonical pattern for optional imports in this project (torch is optional):

```python
_TORCH_AVAILABLE: bool = False
_torch_mod: ModuleType | None = None
_F_mod: ModuleType | None = None

try:
    import torch as _torch_mod
    import torch.nn.functional as _F_mod
    _TORCH_AVAILABLE = True
except ImportError:
    pass

# Public aliases — guarded by assert in each method
torch: ModuleType | None = _torch_mod
F: ModuleType | None = _F_mod
```

After the `if not _TORCH_AVAILABLE: raise RuntimeError(...)` guard, add `assert torch is not None` and `assert F is not None` to narrow types within each method scope.

Do NOT use `# type: ignore[assignment]` for this pattern. Do NOT use `TYPE_CHECKING` (banned by constitution).

### 4. Opaque KV Cache Containers

**Location**: `anvil/services/inference.py`

The KV cache passed to `model.forward(token_id, pos_id, keys, values)` is an opaque container whose type reflects the engine's untyped API. Use `list[list]` rather than `list[list[Any]]`:

```python
keys: list[list] = [[] for _ in range(n_layers)]
values: list[list] = [[] for _ in range(n_layers)]
```

This mirrors the engine's untyped `forward` signature without explicitly writing `Any`.

### 5. Autograd Value Types

**Location**: `anvil/services/inference.py`

Inner functions that inspect `Value._children` and `Value._local_grads` should be typed with `Value` from `anvil.core.autograd`:

```python
from anvil.core.autograd import Value

def assign_op(val: Value) -> str: ...
def traverse(v: Value, depth: int = 0) -> str | None: ...
```

### 6. Callable Parameters

Replace `param: Any = None` with the specific callback signature when known:

```python
# Before
progress_callback: Any = None,
stop_check: Any = None,

# After
progress_callback: Callable[[int, float], None] | None = None,
stop_check: Callable[[], bool] | None = None,
```

### 7. `ignore_errors = true` Overrides

Module-level overrides in `pyproject.toml` are preferred over inline suppressions. Only modules with heavy MLflow integration should retain overrides:

- `anvil.services.mlflow_inputs` — MLflow API boundary, `# type: ignore[attr-defined]` for `LocalArtifactDatasetSource`
- `anvil.services.tracking` — MLflow-heavy, `CapabilityUnavailable` and client types are external

Modules without MLflow stubs issues had their overrides removed.

## Related

- `AGENTS.md` — Line 87: the rule being enforced
- [[Governance/Constitution|Constitution]] — Section "Additional Constraints": the constitutional mandate
- [[Sessions/2026-06-19-mypy-strict-enforcement|Session: Mypy Strict Enforcement]]
