---
title: 028 SaaS Abstraction Framework - research
type: research
tags:
  - type/spec
spec-refs:
  - docs/vault/Specs/028 SaaS Abstraction Framework/
related:
  - '[[028 SaaS Abstraction Framework]]'
created: '2026-06-27'
updated: '2026-06-27'
---

# Research: SaaS Abstraction Framework

**Phase 0 output** — resolves research unknowns for abstraction interface design.

## 1. Interface Design Principles

### Decision
Four focused abstraction interfaces (FileStore, EventBus, JobQueue, ComputeBackend) instead of a single general-purpose "pluggable infrastructure" layer. Each interface maps to one infrastructure concern with distinct lifecycle semantics.

### Rationale
- File I/O (read/write/delete/list) has different constraints than pub/sub messaging (subscribe/publish/close)
- Async job dispatch (submit/cancel/status/list) is a different abstraction than compute execution (run with progress callback)
- Combined interfaces would violate SRP and make contract testing harder
- Following existing codebase patterns (one class per file, focused interfaces)

### Key Findings
| Aspect | Decision |
|--------|----------|
| **FileStore** | `async read/write/delete/list/exists/signed_download_url/signed_upload_url/copy` |
| **EventBus** | `async publish/subscribe/close` with `AsyncIterator[dict]` subscription |
| **JobQueue** | `async submit/cancel/status/list_active` with `TrainingJob` + `ResourceSpec` |
| **ComputeBackend** | `async run(job, event_bus, progress_callback)` returning result dict |

### Alternatives Considered
- Single `StorageBackend` interface: Combines file storage, messaging, and compute — too broad. Rejected.
- Protocol classes (PEP 544): More flexible but harder to enforce at `mypy --strict` level. ABCs chosen for explicitness.
- Abstract base with default implementations: Prefer pure ABCs with no defaults to force correct implementation.

---

## 2. Mode Selection Strategy

### Decision
Two-layer mode selection: (1) entrypoint module as primary switch, (2) `ANVIL_MODE` env var as explicit guard.

### Rationale
- Structural import isolation (FR-011) requires separate entrypoints — no runtime check can prevent `import boto3` if the module is already loaded
- Two-layer approach means a misconfigured deployment fails at process start, never at runtime
- Explicit mode (never auto-detected) prevents silent environment misconfiguration

### Key Findings
| Aspect | Decision |
|--------|----------|
| **Primary switch** | Entrypoint: `anvil.api.app:app` (local) vs `anvil._saas.app:app` (SaaS) |
| **Guard** | `ANVIL_MODE` env var validated against entrypoint at startup |
| **Fail-fast** | Mismatch → clear error with both expected and actual mode printed |
| **SaaS validation** | All required cloud vars checked before any implementation wiring |

### Alternatives Considered
- Single entrypoint with runtime check: SaaS modules would still be imported. Violates FR-011. Rejected.
- Auto-detection based on cloud service availability: Dangerous — a transient network blip could flip mode. Rejected.

---

## 3. ResourceSpec Data Model

### Decision
A structured Pydantic `BaseModel` for compute requirements, making multi-node first-class (FR-040).

### Rationale
- Pydantic provides validation, serialization, and JSON schema generation
- Structured spec (node_count, gpus_per_node, vcpus, memory, instance_class) covers all four compute shapes (cpu, gpu, multi-gpu, multi-node)
- Instance_class as optional lets Batch choose instance type when not specified

### Key Findings
```python
class ResourceSpec(BaseModel):
    node_count: int = 1           # >1 = multi-node parallel Batch job
    gpus_per_node: int = 0        # 0 = CPU-only
    vcpus: int = 2
    memory_mb: int = 4096
    instance_class: str | None = None  # e.g. "g5.xlarge"; None = let Batch choose
```

| `compute_shape` | ResourceSpec |
|-----------------|--------------|
| `cpu` | `node_count=1, gpus_per_node=0` |
| `gpu` | `node_count=1, gpus_per_node=1` |
| `multi-gpu` | `node_count=1, gpus_per_node=N` |
| `multi-node` | `node_count=M, gpus_per_node=N` |

### Alternatives Considered
- Dataclass: Works but lacks validation and schema generation. Pydantic is already a project dependency. ✓
- Named tuple: Immutable but no validation. Rejected.
- Plain dict: No type safety. Rejected.

---

## 4. Contract Testing Strategy

### Decision
A single contract test module (`tests/contract/test_storage_interfaces.py`) exercises all four interfaces against local implementations. The same tests run against SaaS implementations (added in later features) to guarantee parity.

### Rationale
- Contract tests enforce the Liskov Substitution Principle — any implementation that passes the contract is a correct implementation
- Running against local implementations first validates the interface shape before SaaS implementations are written
- Prevents interface drift: if a SaaS implementation cannot pass the contract, the interface needs refinement

### Key Findings
| Aspect | Decision |
|--------|----------|
| **Test framework** | pytest with `@pytest.mark.asyncio` |
| **Fixtures** | One fixture per interface (e.g., `local_file_store`, `in_process_event_bus`) |
| **Coverage** | Every method on every interface tested — positive cases, edge cases, error cases |
| **Isolation** | Tests create fresh implementations per test (no shared state) |

---

## Summary of Architecture Decisions

| Area | Decision | Impact |
|------|----------|--------|
| **Interface design** | Four focused ABCs (FileStore/EventBus/JobQueue/ComputeBackend) | SRP compliance, testable in isolation |
| **Mode selection** | Two-layer: entrypoint + ANVIL_MODE guard | Structural import isolation, fail-fast |
| **ResourceSpec** | Pydantic BaseModel with structured fields | Multi-node first-class, validation |
| **Contract testing** | Common tests for all implementations | Guarantees LSP compliance across modes |
| **File organization** | Interfaces in `anvil/storage/`, implementations in `anvil/_saas/implementations/` | Zero cloud deps in base package |