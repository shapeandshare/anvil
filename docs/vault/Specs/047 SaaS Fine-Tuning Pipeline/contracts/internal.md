---
title: 047 SaaS Fine-Tuning Pipeline — Internal Contracts
type: contract
tags:
  - type/contract
  - domain/training
status: draft
created: '2026-07-02'
updated: '2026-07-02'
---

# Internal Contracts: SaaS Fine-Tuning Pipeline (MVP)

> **MVP scope (2026-07-02):** Provider-backed SaaS backend + adapter-persistence fix. Real
> AWS Batch / `ResourceSpec` / metering / LakeFS / tenancy are DEFERRED (see spec's
> Implementation Scope Note).

## SaasFinetuneProvider (NEW — minimal seam)

File: `anvil/services/compute/saas_finetune_provider.py`

An async Protocol with **exactly three methods** — the stable seam that a real transport
(AWS Batch, a hosted API, etc.) implements later. It MUST NOT grow speculative surface.

```python
class SaasFinetuneProvider(Protocol):
    """Transport seam for remote SaaS fine-tune execution."""

    async def submit(self, config: dict[str, Any]) -> str:
        """Submit a fine-tune job; return an opaque job reference."""

    async def poll_status(self, job_ref: str) -> ComputeStatus:
        """Return the current status of the submitted job."""

    async def fetch_adapter(self, job_ref: str) -> str:
        """Download the completed adapter; return the local artifact path."""
```

**No `ResourceSpec`, no `org_id`, no event-stream types** — YAGNI (Constitution Article XI).
Tests inject a fake implementing this Protocol (mirrors `ModalBackend`'s `function_factory`).

---

## SaasFinetuneBackend (NEW)

File: `anvil/services/compute/saas_finetune_backend.py`

Satisfies `ComputeBackendProtocol` structurally:

```python
class SaasFinetuneBackend:
    name = RegistryBackend.SAAS_FINETUNE  # "saas-finetune"

    def __init__(self, provider: SaasFinetuneProvider | None = None) -> None:
        """Optionally inject a provider (fake in tests, real transport in prod)."""

    @staticmethod
    def is_available() -> bool:
        """Delegate to resolve._saas_configured()."""

    async def run(
        self, docs, config, *, progress_callback, stop_check,
    ) -> ComputeResult:
        """Submit-then-poll (mirrors ModalBackend):
        1. provider.submit(config) -> job_ref; emit progress_callback(-1, 0.0)
        2. poll loop: honor stop_check (cancel -> FAILED); poll_status until terminal
        3. on success: provider.fetch_adapter(job_ref) -> adapter_path
        4. return ComputeResult(status=COMPLETED, adapter_id=<real id>,
           artifact_uris={"adapter_path": adapter_path},
           backend=ComputeBackendResult.SAAS, engine=TrainingEngine.TORCH)
        """
```

### Registration

```python
def _saas_finetune_factory() -> SaasFinetuneBackend:
    return SaasFinetuneBackend()

register(RegistryBackend.SAAS_FINETUNE, _saas_finetune_factory)
```

---

## `_saas_configured()` (fix in `resolve.py`)

Replace the current `return False` stub (lines 193-204) with an env-based check:

```python
def _saas_configured() -> bool:
    """True when a SaaS endpoint is configured (env-based, side-effect-free)."""
    return bool(os.environ.get("ANVIL_SAAS_ENDPOINT"))
```

---

## TrainingService remap fix (`training.py`)

**Current bug** (lines 527-536): the LoRA remap only runs inside
`if backend_name == ComputeBackendResult.LOCAL:`, so a SaaS result never remaps and
`get_backend("saas")` would raise. Add:

```python
# after the existing LOCAL branch:
elif backend_name == ComputeBackendResult.SAAS:
    method = config.get("method", "full")
    if method in ("lora", "qlora"):
        backend_name = RegistryBackend.SAAS_FINETUNE
```

Also extend the `submitted` SSE-event guard (line 560) from `== MODAL` to include
`SAAS_FINETUNE`.

---

## AdapterPersistenceService (NEW — Phase 2 fix)

File: `anvil/services/training/adapter_persistence.py`

```python
class AdapterPersistenceService:
    """Creates a LoRAAdapter DB row from a completed ComputeResult."""

    async def persist(self, result: ComputeResult, config: dict[str, Any]) -> None:
        """When result.adapter_id is set, add a LoRAAdapter row via the repo."""
```

Invoked from the backend-agnostic `on_complete` path — covers both local and SaaS.

---

## Environment Variables (MVP)

| Variable | Default | Description |
|----------|---------|-------------|
| `ANVIL_SAAS_ENDPOINT` | — | Presence enables the SaaS backend (`_saas_configured()`) |

> DEFERRED (not read in MVP): `ANVIL_SAAS_CREDENTIALS_SECRET`, `ANVIL_SAAS_MAX_CONCURRENT`,
> `ANVIL_BATCH_JOB_QUEUE`, `ANVIL_BATCH_JOB_DEFINITION`, `ANVIL_CONFIG_S3_BUCKET` — these
> arrive with the AWS Batch / tenancy follow-on specs.