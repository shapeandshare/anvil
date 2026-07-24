---
title: vllm-mlx as Apple Silicon Serving Backend
type: decision
tags:
  - type/decision
  - domain/inference
  - domain/infrastructure
created: 2026-07-23
updated: 2026-07-23
aliases:
  - ADR-051
  - vllm-mlx Serving Backend
  - Apple Silicon Inference Backend
source: agent
code-refs:
  - anvil/services/compute/
  - anvil/services/inference/
  - anvil/api/v1/models.py
  - pyproject.toml
---

# ADR-051: vllm-mlx as Apple Silicon Serving Backend

## Status

Proposed

## Context

anvil is a desktop-first LLM training workbench that runs primarily on macOS
Apple Silicon.  After fine-tuning a model, users need to **serve** it — expose
it via an API for inference, chat, and downstream consumption.  Currently,
anvil's native inference engine can only run models whose architecture maps
directly to the custom `LlamaModel` (RoPE + SwiGLU + RMSNorm).  Models with
different architectures, or models that benefit from PagedAttention and
continuous batching, are marked `track_only` and cannot be served.

The feedback from visual debugging (2026-07-23) identified this as a blocking
UX gap: users select a model, see no indication it's unsupported, press
"Generate", and get a confusing failure (Report #6, #7).  The immediate fix
added disabled indicators in the dropdown.  The real fix is a serving backend
that can run any model.

### Requirements

- **Serving**, not single-user inference — concurrent requests, continuous
  batching, PagedAttention for long contexts
- **macOS Apple Silicon** as the primary platform (M1/M2/M3/M4/M5)
- **OpenAI-compatible API** so anvil can delegate via standard HTTP
- **Safetensors input** — anvil exports safetensors after fine-tuning
- **Manageable subprocess lifecycle** — anvil starts/stops the server
- **Opt-in dependency** — not everyone needs serving (`[serve]` extra)

## Options Considered

### 1. vllm-mlx (Wayner Barrios)

A purpose-built Apple Silicon inference server that integrates MLX, mlx-lm,
mlx-vlm, and mlx-embeddings under a vLLM-compatible API.  Published at
EuroMLSys '26.

| Metric | Detail |
|--------|--------|
| **Throughput** | ~765 tok/s (Qwen3-0.6B, paged cache); 492 tok/s continuous batching (M1 Max, 64 GB, 5 concurrent) |
| **PagedAttention** | ✅ Yes — Paged KV cache with block sharing, ~1.12x speedup |
| **Continuous batching** | ✅ Yes — 4.3x aggregate throughput at 16 concurrent requests |
| **Prefix caching** | ✅ Yes |
| **SSD-tiered cache** | ✅ Yes |
| **OpenAI API** | ✅ Yes — `/v1/chat/completions`, `/v1/completions` |
| **Auth / rate limiting** | ✅ Built-in (`--api-key`, `--rate-limit`) |
| **Multimodal** | ✅ Vision, audio, embeddings |
| **Conversion needed** | ✅ Yes — safetensors → MLX via `mlx_lm.convert` |
| **Maturity** | Academic paper, active development, production guide exists |
| **Install** | `pip install vllm-mlx` |
| **Serve command** | `vllm-mlx serve <model>` |

### 2. vLLM-Metal (official vLLM project plugin)

A community-maintained hardware plugin that adds MLX as a compute backend
to the standard vLLM engine.

| Metric | Detail |
|--------|--------|
| **Throughput** | No published Apple Silicon benchmarks — expected lower than vllm-mlx due to abstraction overhead |
| **PagedAttention** | ✅ Yes |
| **Continuous batching** | ✅ Yes |
| **Prefix caching** | ⚠️ Experimental |
| **OpenAI API** | ✅ Yes |
| **Auth / rate limiting** | ❌ Requires reverse proxy |
| **Conversion needed** | ✅ Yes — HF/MLX format |
| **Maturity** | Community plugin, less documented, fewer installs |
| **Install** | `pip install vllm-metal` |
| **Serve command** | `vllm serve --device metal <model>` |

**Strongest argument**: one codebase across Linux (CUDA) and macOS (MLX).

### 3. MLX LM Server (Apple official)

Apple's own `mlx_lm.server` shipped in MLX v0.18 (January 2026).

| Metric | Detail |
|--------|--------|
| **Throughput** | ~78 tok/s (Llama 3.1 8B Q4, batch 8, M5 Max) |
| **PagedAttention** | ❌ No |
| **Continuous batching** | ✅ Yes (basic) |
| **Prefix caching** | ⚠️ Basic |
| **OpenAI API** | ✅ Built-in |
| **Auth / rate limiting** | ❌ |
| **Conversion needed** | ✅ Yes — safetensors → MLX via `mlx_lm.convert` |
| **Maturity** | **Very high** — Apple-maintained, ships with MLX |
| **Install** | `pip install mlx-lm` |
| **Serve command** | `mlx_lm.server --model <path>` |

### 4. llama.cpp (GGUF)

| Metric | Detail |
|--------|--------|
| **Throughput** | ~64 tok/s (Llama 3.1 8B Q4, batch 8, M5 Max) |
| **PagedAttention** | ❌ No |
| **Continuous batching** | ✅ Yes (server mode) |
| **Prefix caching** | ✅ Yes |
| **OpenAI API** | ✅ Yes |
| **Conversion needed** | ✅ Yes — safetensors → GGUF via `convert.py` |
| **Maturity** | **Very high** — largest open-source LLM ecosystem |
| **Install** | `pip install llama-cpp-python` or brew |
| **Serve command** | `llama-server -m <model.gguf>` |

### 5. Native PyTorch / Transformers (passthrough)

| Metric | Detail |
|--------|--------|
| **Throughput** | Slowest — no PagedAttention, no batching optimizations |
| **PagedAttention** | ❌ No |
| **Continuous batching** | ❌ No |
| **OpenAI API** | ❌ Must build wrapper |
| **Conversion needed** | ❌ No — loads safetensors directly |
| **Maturity** | Very high, but not designed for serving |
| **Install** | Already behind `[finetune]` extra |

## Decision

**Adopt vllm-mlx as the primary macOS serving backend.**

### Rationale

1. **Throughput for serving** — vllm-mlx is the only option with published
   benchmarks showing multi-concurrent scaling (4.3x at 16 concurrent).  For
   a serving use case this is the decisive metric.

2. **Built-in production features** — `--api-key`, `--rate-limit`, `--timeout`,
   `--use-paged-cache`, `--continuous-batching` are all first-class CLI flags.
   No reverse proxy needed.

3. **Paged KV cache** — essential for serving long-context models with many
   concurrent users.  vllm-mlx's implementation shows block sharing and
   prefix-cache hits saving 2,560 tokens per 10 requests.

4. **SSD-tiered cache** — unique to vllm-mlx among macOS options.  Important
   for models that don't fit entirely in unified memory.

5. **OpenAI API compatibility** — standard integration pattern.  anvil can
   use the OpenAI Python SDK or direct HTTP.

6. **Active development** — EuroMLSys '26 publication, active GitHub, growing
   community.  Not a dead-end.

### Safetensors → MLX conversion

The conversion step is a one-time cost per model:

```bash
mlx_lm.convert --hf-path <safetensors_dir> --mlx-path <output_dir>
```

For anvil-exported models (sub-1B params), this takes ~5–30 seconds.
The converted model is cached and reused across serve sessions.

## Consequences

### Easier

- **Serving any model** — track_only models become servable on macOS
- **Concurrent access** — multiple users/agents can query the same model
- **Standard API** — tools built for OpenAI work out of the box
- **Performance** — quantized inference via MLX is faster than native Python
- **Separation of concerns** — serving backend is a separate process, crash
  isolation from anvil

### Harder

- **Conversion step** — safetensors → MLX adds latency on first serve.
  Mitigated by caching the converted model.
- **Dependency** — `vllm-mlx` is a new dependency for the `[serve]` extra.
  Not installed by default.
- **Process management** — anvil must supervise the vllm-mlx subprocess
  (start, health-check, stop, cleanup).
- **Port management** — must scan for available ports in the 8001-8099 range.
- **No native engine integration** — learning arc widgets (attention viz,
  KV-cache visualization) won't work with served models.  They still use
  the native anvil engine.
- **macOS only** — vllm-mlx is Apple Silicon–specific.  Linux users need
  a different backend (standard vLLM with CUDA).

### Deferred

- **GGUF support** — deferred to a later phase.  llama.cpp is the natural
  choice for GGUF serving, but it requires a separate conversion pipeline
  (safetensors → GGUF) and a different process manager.
- **Multi-model multiplexing** — vllm-mlx supports model swapping, but we
  start with one model per server instance for simplicity.

## Compliance

- The `[serve]` extra installs `vllm-mlx` cleanly
- `POST /v1/models/{id}/serve` returns a 200 with serving URL within 60s
- `POST /v1/models/{id}/stop` terminates the subprocess within 5s
- Subprocess is cleaned up on anvil shutdown
- Converted MLX models are stored at `data/serve/<model_id>/mlx/`
- Tests mock the subprocess and verify API contract

## Implementation Plan

### Phase 1: Foundation (estimated ~485 lines)

1. **`pyproject.toml`** — add `[project.optional-dependencies] serve = ["vllm-mlx"]`
2. **`RunnableStatus`** — add `SERVABLE` value (or equivalent)
3. **`VllmMlxBackend`** — new class in `anvil/services/compute/`:
   - `convert(safetensors_dir) → MLX path`
   - `serve(model_path) → ServeResult { url, port, pid }`
   - `stop(pid) → None`
   - `health() → bool`
4. **`SafetensorsToMlxConverter`** — wraps `mlx_lm.convert` subprocess
5. **API routes** — `POST /v1/models/{id}/serve`, `POST /v1/models/{id}/stop`
6. **Workbench wiring** — property on `AnvilWorkbench` for the backend
7. **UI** — Serve/Stop button on model detail page, status badge in catalog
8. **Tests** — unit tests mocking the subprocess, API contract tests

### Phase 2: Integration (deferred)

1. Chat page routing to served model
2. Inference page routing to served model
3. Auto-stop on idle timeout
4. Dashboard showing active serving sessions

## Performance Comparison Reference

| Backend | ~tok/s | PagedAttn | Cont. Batch | Prefix Cache | Conversion | Maturity |
|---------|-------:|:---------:|:-----------:|:------------:|:----------:|:--------:|
| **vllm-mlx** | **765** | ✅ | ✅ | ✅ | MLX | Academic |
| vLLM-Metal | ? | ✅ | ✅ | ⚠️ | MLX | Community |
| MLX LM | 78 | ❌ | ✅ | Basic | MLX | **Apple** |
| llama.cpp | 64 | ❌ | ✅ | ✅ | GGUF | **Very high** |
| PyTorch | ~10 | ❌ | ❌ | ❌ | None | Very high |

Benchmarks from published sources (vllm-mlx: Qwen3-0.6B with paged cache;
MLX LM: Llama 3.1 8B Q4, batch 8, M5 Max; llama.cpp: same model/config).

## Open Questions and Answers

| Question | Answer |
|----------|--------|
| **Auto-convert on serve, or pre-convert after fine-tuning?** | **Pre-convert**.  Run `mlx_lm.convert` as a post-training step so the Serve button is instant.  Add a `status: converted` field to the model record. |
| **Keep the converted MLX model or regenerate each time?** | **Keep it**.  Conversion is deterministic.  Add `converted_at` timestamp.  Re-convert only if the source safetensors change. |
| **Single model per server, or multi-model multiplexing?** | **Single model per server** for simplicity.  vllm-mlx supports model swapping, but that adds lifecycle complexity.  Multiple models = multiple ports. |
| **What port range?** | `8001-8099` — scan for available ports on serve.  Port recorded in the model record. |
| **Should the server survive anvil restarts?** | **No**.  Manage lifecycle together.  User re-serves after restart.  Converted MLX files persist. |
| **Where to store converted MLX models?** | `data/serve/<model_id>/mlx/` — alongside the safetensors export at `data/models/<model_id>/`. |
| **What about Linux users?** | Future work.  On Linux, the `VllmMlxBackend` would be replaced by a `VllmCudaBackend` using standard vLLM.  Same API, different subprocess. |
| **Do we need auth for the serving endpoint?** | Yes — generate a random API key on serve, pass it to `--api-key`, store it in the model record.  anvil uses it for internal requests; external callers get it from the UI. |

## See Also

- [[Decisions/ADR-015-pluggable-compute-backends|ADR-015: Pluggable Compute Backends]]
- [[Decisions/ADR-039-client-sdk-architecture|ADR-039: Client SDK Architecture]]
- [[Decisions/README|Decisions]]
- [vllm-mlx GitHub](https://github.com/waybarrios/vllm-mlx)
- [vllm-mlx benchmarks](https://github.com/waybarrios/vllm-mlx/blob/main/docs/benchmarks/llm.md)
- [vLLM-Metal installation](https://github.com/vllm-project/vllm/blob/main/docs/getting_started/installation/gpu.apple.inc.md)
- [MLX LM server docs](https://github.com/ml-explore/mlx-examples/tree/main/llms#mlx-lm-server)
