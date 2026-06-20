---
title: Glossary
type: reference
tags: [type/reference, domain/governance]
created: 2026-06-10
updated: 2026-06-19
---

# Glossary

| Term | Definition |
|------|------------|
| **anvil** (core engine) | The core Llama training engine — ~200 lines of pure Python, zero dependencies |
| **God Class** | `AnvilWorkbench` — single entry point exposing all service methods to routes/CLI/tests |
| **FileStore** | Pluggable async file storage abstraction (local filesystem or S3) |
| **Repository** | Data access class encapsulating all DB operations for a single entity |
| **SSE** | Server-Sent Events — unidirectional HTTP streaming for real-time updates |
| **UoW** | Unit of Work — transaction boundary spanning multiple repository operations |
| **ADR** | Architecture Decision Record — documents significant architecture decisions |
| **Vault** | Obsidian-compatible documentation directory at `docs/vault/` |
| **Constitution** | Project governance document (`.specify/memory/constitution.md`) defining non-negotiable principles |
| **Value** | Autograd scalar node in `anvil/core/autograd.py` — stores `data`, `grad`, children and local partial derivatives for reverse-mode AD |
| **Autograd** | Automatic differentiation via computation graph — forward pass builds DAG, `.backward()` traverses in topological order applying chain rule |
| **KV Cache** | Key-Value cache for causal self-attention — per-layer lists appended at each autoregressive step, avoids recomputing previous positions |
| **RMSNorm** | Root Mean Square Layer Normalization — `x / sqrt(mean(x²) + ε)` — the base computation is stateless; learned scale parameters (`rms_1`, `rms_2`, `rms_final`) are applied elementwise after normalization. Applied at three positions: pre-attention (per-layer), pre-MLP (per-layer), and pre-output (once). No embedding-level normalization |
| **Adam** | Adaptive Moment Estimation optimizer — bias-corrected first/second moment estimates (m, v) + linear LR decay, implemented manually in `train()`. NOTE: this is plain Adam, NOT AdamW — the update rule (`p.data -= lr_t * m_hat / (v_hat**0.5 + 1e-8)`) has no weight-decay term. The GPU backend uses `torch.optim.Adam` (also no weight decay) |
| **BOS** | Begin-of-Sequence sentinel token — always `len(uchars)` (last index in vocabulary), used to delimit documents and stop sampling |
| **Autoregressive** | Generating one token at a time, conditioning each prediction on all previous tokens via the KV cache |
| **Softmax** | Normalized exponential function — `e^x_i / Σ e^x_j` — converts logits to probability distribution over vocabulary |
| **Cross-Entropy** | Loss function for classification — `-log(p_target)` — negative log probability of the correct next token |
| **State Dict** | The model's parameter dictionary — maps weight names (wte, lm_head, rms_final, layer.N.{attn_wq/wk/wv/wo, mlp_gate/up/down, rms_1/rms_2}) to lists of Value objects (2D matrices for weights, 1D vectors for norm scales). No wpe, no fc1/fc2 — those were removed in the Llama evolution. See [[SafetensorsExport]] for how these map to HF tensor names |
| **Safetensors** | Safe serialization format for neural network tensors. anvil exports trained models to safetensors (`.safetensors` files) with HuggingFace-compatible tensor names, config, and tokenizer metadata. See [[SafetensorsExport]] |
| **RoPE** | Rotary Position Embedding — encodes token position by rotating Query and Key vectors by an angle proportional to position. Half-split (rotate_half) convention: dim i paired with dim i + head_dim/2. No learned position parameters. See `apply_rope()` in `anvil/core/engine.py` |
| **SwiGLU** | SiLU-gated gated MLP — replaces ReLU with `(SiLU(x·Wgate) ⊙ x·Wup)·Wdown`. Three projections (gate, up, down) with `intermediate_size = int(8 × n_embd / 3)` preserving parameter count parity. See `engine.py:195-200` |
| **Dual Backend** | anvil's CPU and GPU training backends. CPU (`train()`) uses pure Python with Value autograd. GPU (`train_torch()`) uses PyTorch tensors. Identical architecture enforced by code review. See [[DualBackend]] |
| **GPU Bridge** | `_load_weights_into_model()` — copies GPU-trained weight lists into a CPU LlamaModel for downstream compatibility. Requires architecture parity between backends. See `training.py:19-35` |
| **Dataset** | Static collection of text samples where each line in a `.txt` file becomes one training sample. Uploaded manually or created empty. Supports inline editing, curation (dedup, filter, replace), and export. Best for curated/fine-tuning data. |
| **Corpus** | Dynamic directory source scanned with glob patterns and chunking strategies (windowed/file/line). Supports gitignore-style include/exclude filtering. Read-only from source (no inline sample editing). Best for code repos and large directory trees. |
| **Run-in-Executor** | Python asyncio pattern for offloading blocking/sync code to a thread pool thread, used by `TrainingService` to run the core engine |
| **Commitizen** | CLI tool for conventional commit enforcement and semantic version bump management (`cz commit`, `cz bump`, `cz check`) |
| **Conventional Commits** | Structured commit message format: `<type>(<scope>): <description>` — types: feat, fix, perf, refactor, chore, docs, ci, test, style, build |
| **SemVer** | Semantic Versioning (`MAJOR.MINOR.PATCH`) — bump rules: fix→PATCH, feat→MINOR, BREAKING CHANGE→MAJOR |
| **BUMP_PAT** | Fine-grained GitHub Personal Access Token used by CI workflows to create auto-merge PRs (Contents+PRs+Workflows: write) |
| **ANVIL_MODE** | Env var selecting operating mode (`local` or `saas`). A guard + config selector, not the primary switch — the entrypoint module is (`anvil.api.app` vs `anvil._saas.app`). Never auto-detected. See [[SaaSArchitecture]] |
| **Three-Mode Model** | anvil's operating modes: Local User (pip install, SQLite, in-process), SaaS User (hosted multi-tenant on AWS), SaaS Developer (docker compose / dev AWS / cdk). Same package, infra swapped behind four interfaces. See [[SaaSArchitecture]] |
| **EventBus** | Pluggable async pub/sub abstraction for live training metrics. Local = `InProcessEventBus` (asyncio.Queue); SaaS = `RedisEventBus` (ElastiCache). Delivery-only — never the source of truth (AD-4) |
| **JobQueue** | Pluggable training-job dispatch abstraction. Local = `InProcessJobQueue` (immediate task); SaaS = `BatchJobQueue` (AWS Batch submit). Carries a `ResourceSpec` |
| **ComputeBackend** | Pluggable training execution abstraction. Local = stdlib/torch in-process; SaaS = `BatchComputeBackend` (Batch on EC2: CPU/GPU/multi-node) |
| **ResourceSpec** | Structured compute requirement `{node_count, gpus_per_node, vcpus, memory_mb, instance_class}` — makes multi-node training a first-class job shape (AD-1) |
| **Organization** | Top-level tenant and billing boundary in SaaS mode. Owns all resources; no query crosses `org_id`. Root of the RBAC hierarchy (AD-8) |
| **Team** | A group of users within an Organization; resources may be team-scoped. Users may belong to multiple teams (AD-8) |
| **Role** | RBAC role — `owner`/`admin`/`member`/`viewer`. Assigned at org level, optionally overridden per team. Governs permitted actions (AD-8) |
| **JobEvent** | Append-only lifecycle event `(job_id, sequence)` in PostgreSQL — the authoritative record of training-job state. `TrainingJob.status` is derived from the latest event (AD-4) |
| **Reconciler** | Scheduled task that compares Batch/DB/MLflow/S3 state and repairs jobs stuck in non-terminal states beyond a grace period — the self-healing backstop (AD-4) |
| **UsageRecord** | Per-job billback record (GPU-seconds, instance-hours) attributed to `org_id`/`team_id`/`user_id`, derived from terminal `JobEvent` (AD-9) |
| **Cognito** | Amazon Cognito User Pools — the SaaS identity provider. App-managed OIDC/JWT (validated via `aws-jwt-verify` + JWKS), native users default, social login BYO (AD-2/AD-3) |
| **RDS Proxy + IAM Auth** | DB access pattern for SaaS — pods generate short-lived (≤15 min) IAM tokens from their role; no static DB password ever reaches a pod (AD-11 / FR-045c) |
| **anvil deploy** | Turnkey CLI deploying the full SaaS stack into any AWS account via pre-synthesized, digest-pinned CloudFormation through boto3 — no Node.js/CDK on the user's machine (AD-7). Includes `verify` 3-layer validation |
| **Compute Shape** | One of `cpu`/`gpu`/`multi-gpu`/`multi-node` — selects the pre-registered Batch job definition and queue (AD-1/AD-11) |
