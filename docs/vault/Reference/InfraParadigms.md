---
created: '2026-06-16'
tags:
  - type/reference
  - domain/infrastructure
  - domain/mlops
title: ML Infrastructure Landscape — Paradigms & Vendors
type: reference
updated: '2026-06-16'
related:
  - '[[Reference/ContentManagementLandscape]]'
---
# ML Infrastructure Landscape — Paradigms & Vendors

> Reference taxonomy for reasoning about ML infrastructure layers. Companion to [[Decisions/ADR-014-ml-infrastructure-tier-strategy|ADR-014]].

## Grounding Reality: Where anvil Sits Today

anvil's `train_torch()` runs **single-example, single-token Python-loop forward passes** — no batching, no vectorized sequence dimension — on tiny models (`n_embd=16`, `n_layer=1`). This means:

- **anvil is not GPU-bound today.** A B200 won't beat an M-series laptop here — the `for pos_id in range(n)` Python loop dominates.
- **"External compute" is about lifecycle management, reproducibility, and parallel experiment fan-out** — not raw FLOPs.
- **The integration surface is tiny and portable:** Python 3.11 + optional PyTorch + MLflow client + S3-compatible artifact store + SQLite metadata.
- **The single highest-leverage move before any GPU vendor matters:** batch `train_torch` over the sequence dimension. Kill the `for pos_id` Python loop.

## The 5 Paradigms

| # | Paradigm | What it gives you | What it does NOT give | Example |
|---|----------|-------------------|----------------------|---------|
| 1 | **Raw IaaS GPU/CPU** | A box. You SSH or containerize. | Tracking, registry, scheduling | AWS EC2, Lambda Labs, Hetzner |
| 2 | **Serverless / ephemeral GPU** | Decorate a Python fn → runs in cloud, scale-to-zero | Heavy orchestration; you wire tracking | Modal, RunPod, Beam |
| 3 | **Workflow / pipeline orchestrators** | DAGs, retries, parallel sweeps, lineage | Compute (BYO); often no serving UI | Metaflow, ZenML, Prefect, Airflow |
| 4 | **Full MLOps platforms** | Train + track + registry + serve + monitor | Portability (lock-in risk) | SageMaker, Vertex, Determined AI |
| 5 | **Tracking / registry SaaS** | Lifecycle metadata layer | Compute | MLflow (self-host), W&B, HF Hub |

> "Metaflow + MLflow" = paradigm 3 (orchestration) + paradigm 5 (tracking). Two different layers, separable.

## Full Vendor Landscape

### 1 — Raw IaaS GPU/CPU

| Vendor | Hardware | Lock‑in | Notes |
|--------|----------|---------|-------|
| AWS EC2 (g5/g6/p5, Graviton) | NVIDIA, Trainium, ARM | 🟢 / 🔴 Trainium | Pair with `make docker`. Trainium = 🔴 (Neuron SDK). |
| GCP Compute Engine | NVIDIA, TPU | 🟢 / 🔴 TPU | TPU needs JAX/XLA — not anvil's stack. |
| Lambda Labs / CoreWeave / Crusoe | NVIDIA-only | 🟢 | Cheapest pure GPU. Great low-lock default. |
| Hetzner / OVH / bare metal | CPU + some GPU | 🟢 | For anvil's CPU-bound profile, a cheap big CPU box is the rational pick. |

### 2 — Serverless / ephemeral GPU

| Vendor | Lock‑in | Notes |
|--------|---------|-------|
| **Modal** | 🟡 | Decorate a Python fn, scale-to-zero, mounts S3. Minimal refactor — wraps `train_torch` directly. **Top pick for fan-out experiments at current scale.** |
| RunPod / Vast.ai | 🟢 | Container in, container out. Cheapest spot GPUs. |
| Beam / Replicate / Baseten | 🟡–🔴 | More serving-oriented. Replicate uses Cog format (🔴-ish). |

### 3 — Workflow / pipeline orchestrators

| Tool | Type | Lock‑in | Notes |
|------|------|---------|-------|
| Metaflow (Netflix, OSS) | OSS + AWS backend | 🟡 | Python-native, `@step` / `@batch`. Plays with any compute + MLflow. |
| Prefect / Dagster | OSS | 🟢 | General orchestration. Dagster has nice asset/lineage model. |
| Apache Airflow | OSS | 🟢 | Heavyweight, ubiquitous, not ML-specific. |
| Flyte / Union.ai | OSS / SaaS | 🟡 | Strong typing + lineage, K8s-native. |
| Kubeflow Pipelines | OSS on K8s | 🟡 | Only if you already run Kubernetes. |
| **ZenML** | OSS | 🟢 | Thin portable abstraction over orchestrator+tracker+registry. Designed to avoid lock-in. Worthy of serious look. |

### 4 — Full managed MLOps platforms

| Vendor | Lock‑in | Notes |
|--------|---------|-------|
| AWS SageMaker | 🔴 | Training jobs + registry + endpoints. Powerful, deep AWS coupling. |
| GCP Vertex AI | 🔴 | Same story on Google. |
| Azure ML | 🔴 | Same on Azure. |
| Databricks (Managed MLflow + Jobs) | 🟡 | Least-friction managed option — tracking code barely changes. |
| Determined AI (HPE, OSS core) | 🟡 | Best-in-class for distributed training + sweeps if you outgrow single-node. |
| ClearML | 🟢–🟡 | OSS, all-in-one, self-hostable. Strong anti-lock-in all-rounder. |

### 5 — Tracking / registry SaaS

| Vendor | Lock‑in | Notes |
|--------|---------|-------|
| **MLflow (self-host / OSS)** | 🟢 | Already in place. Keep it as the portable core. |
| Weights & Biases | 🟡 | Best UX for experiment comparison; SDK-coupled. |
| Neptune.ai / Comet | 🟡 | W&B alternatives. |
| **Hugging Face Hub** | 🟢 | Already export safetensors → push models here. Free registry + sharing. Near-zero lock-in. |

## Cross-Cutting Dimensions

| Dimension | Lowest lock‑in choice | Highest capability choice | anvil note |
|-----------|-----------------------|---------------------------|------------|
| Vendor lock-in | RunPod/Lambda + self-host MLflow + HF Hub | SageMaker/Vertex/Azure ML | Safetensors + MLflow already make you portable — don't surrender that. |
| Ecosystem | Python/PyTorch-native everywhere | TPU/JAX, Trainium/Neuron | Avoid TPU/Trainium — wrong language/framework. |
| Libraries | `torch` + `mlflow` only | Platform SDKs | Keep deps thin (matches lean dependency ethos). |
| Hardware | CPU box (Hetzner) — honest fit today | NVIDIA H100/B200 cluster | GPUs wasted until the engine batches the sequence loop. |
| Programming language | Pure Python | — | Every red-flag option (TPU/Trainium) implies a language/compiler shift. |

## See Also

- [[Decisions/ADR-014-ml-infrastructure-tier-strategy]] — The tiered adoption strategy
- [[ArchitectureOverview]] — Where the training engine lives
- [[TrainingDataFlow]] — Detailed training loop
- [[OpenQuestions]] — Engine bottleneck as open item
