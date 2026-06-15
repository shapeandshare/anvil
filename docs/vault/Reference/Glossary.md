---
title: Glossary
type: reference
tags: [type/reference, domain/governance]
created: 2026-06-10
updated: 2026-06-14
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
| **Constitution** | Project governance document (`CONSTITUTION.md`) defining non-negotiable principles |
| **Value** | Autograd scalar node in `anvil/core/autograd.py` — stores `data`, `grad`, children and local partial derivatives for reverse-mode AD |
| **Autograd** | Automatic differentiation via computation graph — forward pass builds DAG, `.backward()` traverses in topological order applying chain rule |
| **KV Cache** | Key-Value cache for causal self-attention — per-layer lists appended at each autoregressive step, avoids recomputing previous positions |
| **RMSNorm** | Root Mean Square Layer Normalization — `x / sqrt(mean(x²) + ε)` — the base computation is stateless; learned scale parameters (`rms_1`, `rms_2`, `rms_final`) are applied elementwise after normalization. Applied at three positions: pre-attention (per-layer), pre-MLP (per-layer), and pre-output (once). No embedding-level normalization |
| **AdamW** | Adam optimizer with weight decay — bias-corrected moment estimates + linear LR decay, implemented manually in `train()` |
| **BOS** | Begin-of-Sequence sentinel token — always `len(uchars)` (last index in vocabulary), used to delimit documents and stop sampling |
| **Autoregressive** | Generating one token at a time, conditioning each prediction on all previous tokens via the KV cache |
| **Softmax** | Normalized exponential function — `e^x_i / Σ e^x_j` — converts logits to probability distribution over vocabulary |
| **Cross-Entropy** | Loss function for classification — `-log(p_target)` — negative log probability of the correct next token |
| **State Dict** | The model's parameter dictionary — maps weight names (wte, lm_head, rms_final, layer.N.{attn_wq/wk/wv/wo, mlp_gate/up/down, rms_1/rms_2}) to lists of Value objects (2D matrices for weights, 1D vectors for norm scales). No wpe, no fc1/fc2 — those were removed in the Llama evolution |
| **Run-in-Executor** | Python asyncio pattern for offloading blocking/sync code to a thread pool thread, used by `TrainingService` to run the core engine |
| **Commitizen** | CLI tool for conventional commit enforcement and semantic version bump management (`cz commit`, `cz bump`, `cz check`) |
| **Conventional Commits** | Structured commit message format: `<type>(<scope>): <description>` — types: feat, fix, perf, refactor, chore, docs, ci, test, style, build |
| **SemVer** | Semantic Versioning (`MAJOR.MINOR.PATCH`) — bump rules: fix→PATCH, feat→MINOR, BREAKING CHANGE→MAJOR |
| **BUMP_PAT** | Fine-grained GitHub Personal Access Token used by CI workflows to create auto-merge PRs (Contents+PRs+Workflows: write) |
