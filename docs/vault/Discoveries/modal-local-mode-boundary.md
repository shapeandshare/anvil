---
title: Modal Local-Mode-Only Boundary
type: discovery
status: draft
source: agent
related:
  - '[[Decisions/ADR-015-pluggable-compute-backends|ADR-015]]'
  - '[[Decisions/ADR-030-saas-architecture|ADR-030]]'
  - '[[Reference/DualBackend]]'
  - '[[Specs/016 SaaS Architecture/spec]]'
code-refs:
  - anvil/services/compute/modal_backend.py
  - anvil/services/compute/compute_backend.py
  - anvil/services/compute/resolve.py
  - docs/vault/Specs/016 SaaS Architecture/contracts/compute_backend.py
session: '2026-06-21'
created: '2026-06-22'
updated: '2026-06-22'
summary: ModalBackend is explicitly a local-mode compute option, never a SaaS-mode
  compute path. This note documents the boundary, the gaps that prevent Modal from
  serving as a SaaS backend, and the cross-references that enforce the split.
tags:
  - type/discovery
  - domain/architecture
  - domain/infrastructure
  - status/draft
aliases:
  - Modal Local-Mode-Only Boundary
---

ModalBackend is a local-mode cloud GPU option, not a SaaS-mode compute path. The
three-mode architecture (ADR-030) assigns Modal to the local mode column alongside
LocalStdlibBackend and LocalTorchBackend. SaaS mode uses AWS Batch via
`BatchComputeBackend` in `anvil/_saas/implementations/`.

The contract specification at `docs/vault/Specs/016 SaaS Architecture/contracts/compute_backend.py`
explicitly lists Modal as a local-mode implementation. The SaaS architecture spec's
feature matrix (FR-005, FR-039, AD-1) defines AWS Batch on EC2 as the exclusive
SaaS compute substrate. ADR-030 lists Modal under "Existing compute backends preserved
— local-stdlib, local-torch, modal still work in local mode."

## Why Modal Cannot Serve as a SaaS Compute Backend

The SaaS compute spec (FR-039 through FR-045m, AD-1) requires capabilities that
ModalBackend does not and should not implement:

- **job_events append-only table** (FR-043): SaaS mode requires PostgreSQL as the
  source of truth for job lifecycle, with an append-only `job_events` table and a
  reconciler for stuck-job repair. ModalBackend uses `call.get_status()` polling
  with no durable event log.
- **ResourceSpec** (FR-040): SaaS mode expresses compute requirements as a structured
  `{node_count, gpus_per_node, vcpus, memory_mb, instance_class}` spec. ModalBackend
  takes a flat `config` dict — it cannot express multi-node or multi-GPU-per-node shapes.
- **EventBus integration** (FR-004): SaaS mode streams SSE metrics via Redis pub/sub.
  ModalBackend uses a direct `progress_callback` — no pub/sub, no pod-failover replay.
- **IAM auth chain** (FR-045c): SaaS mode uses RDS Proxy + IAM database authentication.
  ModalBackend uses `modal.Secret.from_name("mlflow-secret")` — a fundamentally
  different credential model.
- **S3 config-object pattern** (FR-045h): SaaS compute pods receive only pointers
  (`JOB_ID`, `CONFIG_S3_KEY`) and fetch data from S3. ModalBackend passes `docs`
  and `config` directly as function arguments.
- **Checkpointing** (FR-045m): SaaS mode requires periodic S3 checkpoints for
  Spot-interruption retry. ModalBackend has no checkpoint support.
- **Usage metering** (FR-046): SaaS mode derives `usage_record` from job lifecycle.
  ModalBackend does not track GPU-seconds or instance-hours.

## Cross-References Enforcing the Boundary

| Artifact | What it says |
|---|---|
| `contracts/compute_backend.py` lines 50-56 | Lists ModalBackend under "Implementations (existing, in anvil/services/compute/)" and BatchComputeBackend under "New implementation (in anvil/_saas/implementations/)" |
| `Specs/016 SaaS Architecture/spec.md` FR-005, FR-039 | SaaS dispatches training to AWS Batch on EC2 |
| ADR-030 Consequences (Positive) | "Existing compute backends preserved — local-stdlib, local-torch, modal still work in local mode" |
| `Reference/SaaSArchitecture.md` feature matrix | "Training (modal)": ✅ local, ❌ SaaS, ❌ Developer |
| `Reference/DualBackend.md` Compute Backend Registry | Registry maps `"modal"` to ModalBackend; the compute backend abstraction applies only to local mode |
| `anvil/services/compute/resolve.py` | `"modal"` raises `ComputeBackendUnavailable` if the modal package is not installed (D4 rule: must never silently fall back) |

## Implications

- **No split-brain**: Because `ANVIL_MODE=saas` loads a different entrypoint
  (`anvil/_saas/`) that has no import path to `anvil/services/compute/modal_backend.py`,
  the Modal code path is structurally unreachable in SaaS mode. This is enforced by
  the FR-011 import isolation rule.
- **Bridge scenario foreclosed**: Using Modal as an interim SaaS compute backend
  would require deliberately importing Modal from `anvil/_saas/` and bypassing the
  BatchJobQueue abstraction. This is technically possible but would diverge from
  the ADR-030/ADR-015 architecture — the gap analysis above shows the missing
  capabilities.
- **Future backends**: New remote backends (SkyPilot, Metaflow) follow the same
  rule — they belong in local mode unless explicitly specified in the SaaS
  architecture spec via a new ADR.

## References

- `docs/vault/Decisions/ADR-015-pluggable-compute-backends`
- `docs/vault/Decisions/ADR-030-saas-architecture.md`
- `docs/vault/Specs/016 SaaS Architecture/spec.md`
- `docs/vault/Specs/016 SaaS Architecture/contracts/compute_backend.py`
- `docs/vault/Reference/DualBackend.md`
- `docs/vault/Reference/SaaSArchitecture.md`
- `anvil/services/compute/modal_backend.py`
- `anvil/services/compute/compute_backend.py`
- `anvil/services/compute/resolve.py`