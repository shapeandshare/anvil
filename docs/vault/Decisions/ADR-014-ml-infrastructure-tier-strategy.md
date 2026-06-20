---
created: '2026-06-16'
tags:
- type/decision
- domain/infrastructure
- domain/mlops
title: ML Infrastructure Tier Strategy — Compute & Orchestration Trajectory
type: decision
updated: '2026-06-16'
aliases:
- ML Infrastructure Tier Strategy — Compute & Orchestration Trajectory
source: agent
code-refs:
- anvil/services/tracking/tracking_service.py
- anvil/services/training/export.py
- docs/vault/Reference/InfraParadigms.md
---
# ADR-014: ML Infrastructure Tier Strategy — Compute & Orchestration Trajectory

## Status
Accepted

## Context
anvil currently runs training on a local laptop (CPU or Apple MPS) with a self-hosted MLflow tracking server managed by the supervisor. As the project matures, we need a clear, lock-in-aware trajectory for scaling compute and orchestration — one that matches anvil's actual graph (CPU-bound toy scale → parallel sweeps → distributed GPU) without defaulting to enterprise overkill.

The core tension: ML infrastructure vendors compete on lock-in. Every platform (SageMaker, Vertex, Databricks, Determined AI) wants to own your compute _and_ your tracking _and_ your orchestration. anvil should adopt at most one layer at a time, keeping each layer separable.

## Decision

Adopt a **tiered infrastructure strategy** based on actual need, not hypothetical scale. Each tier is a stepping stone — skip none, advance only when the current tier genuinely bottlenecks.

### Tier 0 — Today (CPU-bound toy scale)

**Stack**: Self-hosted MLflow + safetensors → Hugging Face Hub push.

**Compute**: Local laptop (CPU / MPS). For off-laptop runs:
- **Modal** (paradigm 2 — serverless functions wrapping `train_torch`)
- **OR** RunPod / Hetzner container via existing `make docker`

**Tracking**: Keep the existing self-hosted MLflow server (supervisor-managed).

**Artifact**: Safetensors export, `huggingface-cli upload` for sharing.

**Lock-in**: 🟢 Green — MLflow is replaceable (open format), containers are portable, Hugging Face Hub is the industry standard for distribution.

**Effort**: Hours.

### Tier 1 — Parallel experiment sweeps & lineage

**Trigger**: You need to run 10+ experiments in parallel and track their DAG lineage.

**Stack**: Metaflow or ZenML as the **orchestrator** on top of Modal/RunPod compute. MLflow **stays as the tracker only**.

**Key constraint**: Orchestration and tracking remain separable. Metaflow/ZenML call MLflow's API — they don't replace it. This is the "Metaflow + MLflow" instinct done right.

**Lock-in**: 🟡 Yellow — orchestrator swap is non-trivial but the tracking layer (MLflow) remains portable. The compute layer (Modal/RunPod) is independently swappable.

### Tier 2 — Distributed GPU sweeps

**Trigger**: The engine is vectorized (torch) and genuinely needs NVIDIA GPUs at scale.

**Stack**:
- **Compute**: NVIDIA GPUs on Lambda Labs / CoreWeave (not AWS — worse price/performance for non-Kubernetes workloads).
- **Orchestration**: Determined AI (native PyTorch integration, built for distributed sweeps) or Databricks Jobs (if the team is already on Databricks).
- **Tracking**: MLflow stays — Determined AI has its own tracking but we suppress it in favor of MLflow for consistency.

**Lock-in**: 🟡 Yellow — Determined AI has a migration path, CoreWeave/Lambda are standard K8s underneath.

### Explicit Non-Goals (Avoid unless mandated)

| Platform | Lock-in | Reason to avoid |
|----------|---------|-----------------|
| SageMaker / Vertex AI / Azure ML | 🔴 Red | Proprietary APIs, managed notebook lock-in,昂贵. anvil is not an enterprise MLOps platform. |
| TPU / Trainium | 🔴 Red | Wrong ecosystem (JAX/XLA), wrong language (Python-only, but anvil is stdlib-first). Only consider if the engine itself migrates to JAX. |

## Consequences

**Easier**:
- Each tier is independently adoptable — no premature commitment to any vendor.
- MLflow remains the constant tracking layer through all three tiers; experiment history never needs migration.
- Container-based compute (Modal/RunPod/Docker) means the training engine stays platform-agnostic.
- Tier 0 is hours of effort — no new dependencies, no new services.

**Harder**:
- Must resist the temptation to skip tiers ("we might need distributed GPU later, just set up Determined AI now"). Premature orchestration adds complexity with no benefit at toy scale.
- Tier 1 requires learning Metaflow or ZenML — real cognitive overhead that must be justified by actual parallel sweep demand.
- Tier 2 depends on the engine being vectorized (torch) — no sense shopping for NVIDIA GPUs until the engine actually saturates them.

## See Also

- [[Reference/InfraParadigms]] — Full vendor landscape table, 5-paradigms taxonomy, cross-cutting dimensions framework, and the grounding reality about anvil's single-token training loop bottleneck.
- [[Reference/OpenQuestions]] — Engine batching as the highest-leverage prerequisite for GPU vendor adoption.

## Compliance

- Tier advances are gated on demonstrated bottleneck, not hypothetical need.
- No orchestration framework is added without a concrete use case (5+ parallel experiments blocked by current serial runner).
- No enterprise MLOps platform (SageMaker/Vertex/Azure ML) is adopted unless explicitly mandated by the organization hosting the project.
- TPU/Trainium is out of scope unless the core engine migrates away from stdlib Python.
- This ADR is reviewed when the first off-laptop compute run is configured (Tier 0 → Tier 1 boundary).
