---
title: Glossary
type: reference
tags: [type/reference, domain/governance]
created: 2026-06-10
updated: 2026-06-12
---

# Glossary

| Term | Definition |
|------|------------|
| **microgpt** | The core GPT training engine — ~200 lines of pure Python, zero dependencies |
| **God Class** | `MicroGPTWorkbench` — single entry point exposing all service methods to routes/CLI/tests |
| **FileStore** | Pluggable async file storage abstraction (local filesystem or S3) |
| **Repository** | Data access class encapsulating all DB operations for a single entity |
| **SSE** | Server-Sent Events — unidirectional HTTP streaming for real-time updates |
| **UoW** | Unit of Work — transaction boundary spanning multiple repository operations |
| **ADR** | Architecture Decision Record — documents significant architecture decisions |
| **Vault** | Obsidian-compatible documentation directory at `docs/vault/` |
| **Constitution** | Project governance document (`CONSTITUTION.md`) defining non-negotiable principles |
| **Value** | Autograd scalar node in `microgpt/core/autograd.py` — stores `data`, `grad`, children and local partial derivatives for reverse-mode AD |
| **Autograd** | Automatic differentiation via computation graph — forward pass builds DAG, `.backward()` traverses in topological order applying chain rule |
| **KV Cache** | Key-Value cache for causal self-attention — per-layer lists appended at each autoregressive step, avoids recomputing previous positions |
| **RMSNorm** | Root Mean Square Layer Normalization — `x / sqrt(mean(x²) + ε)` — used in GPT forward pass at three points per layer |
| **AdamW** | Adam optimizer with weight decay — bias-corrected moment estimates + linear LR decay, implemented manually in `train()` |
| **BOS** | Begin-of-Sequence sentinel token — always `len(uchars)` (last index in vocabulary), used to delimit documents and stop sampling |
| **Autoregressive** | Generating one token at a time, conditioning each prediction on all previous tokens via the KV cache |
| **Softmax** | Normalized exponential function — `e^x_i / Σ e^x_j` — converts logits to probability distribution over vocabulary |
| **Cross-Entropy** | Loss function for classification — `-log(p_target)` — negative log probability of the correct next token |
| **State Dict** | The model's parameter dictionary — maps weight names (wte, wpe, lm_head, layer.N.attn_w*) to matrix of Value objects |
| **Run-in-Executor** | Python asyncio pattern for offloading blocking/sync code to a thread pool thread, used by `TrainingService` to run the core engine |
