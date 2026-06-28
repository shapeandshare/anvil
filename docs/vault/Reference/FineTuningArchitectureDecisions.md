---
title: Fine-Tuning Architecture Decisions (FT-AD-1..11)
type: reference
tags:
  - type/reference
  - domain/training
  - domain/architecture
created: '2026-06-28'
updated: '2026-06-28'
aliases:
  - Fine-Tuning Architecture Decisions
  - FT-AD-1..11
status: draft
---
# Fine-Tuning Architecture Decisions (FT-AD-1..11)

The canonical, binding architecture decisions for anvil's **fine-tuning body of work**. These are the
**shared substrate** referenced by the per-feature fine-tuning specs (039–049), decomposed from the
umbrella spec [[Specs/038 Fine-Tuning Arc/038 Fine-Tuning Arc|038 Fine-Tuning Arc]].

> **Provenance**: Authored alongside the umbrella spec `038 Fine-Tuning Arc - spec.md`. This note is
> the durable home for the decisions so every child spec links to one authoritative source — mirroring
> how [[Reference/SaaSArchitectureDecisions|SaaS Architecture Decisions]] serve specs 028–037.

> **Relationship to SaaS decisions**: Fine-tuning reuses the SaaS compute/storage substrate where it
> exists. FT-AD references AD-1 (Batch compute), AD-4 (job_events), AD-17 (LakeFS content repo)
> rather than redefining them.

## Decision Index

| FT-AD | Decision | Primary spec(s) |
|-------|----------|-----------------|
| FT-AD-1 | Two distinct fine-tuning modes — **Native warm-start** (anvil's own char-level model) and **External PEFT** (HF pretrained + LoRA/QLoRA) — behind one compute seam | 039, 044 |
| FT-AD-2 | Heavy ML deps (`torch`, `transformers`, `peft`, `huggingface_hub`, `datasets`) live in **optional extras only**; base `pip install anvil` is unchanged | 039, 044 |
| FT-AD-3 | **Tokenizer abstraction** — a model carries its tokenizer as a first-class artifact; the abstraction holds both char-level (native) and HF subword tokenizers | 043 |
| FT-AD-4 | External models enter via a **source-agnostic Import paradigm** — `ModelSource` interface, HuggingFace Hub first, local-file import second; a metadata entry is created *before* assets download | 040, 041 |
| FT-AD-5 | Model assets are **tracked through existing governance** — weights/tokenizer/config are managed assets; local filesystem now, **LakeFS (AD-17)** under SaaS | 042 |
| FT-AD-6 | Fine-tuning runs through the **existing `ComputeBackendProtocol`** — a fine-tune is a job with `base_model_ref`; `resolve.py` routes local vs SaaS by `ResourceSpec`/model size | 046, 047 |
| FT-AD-7 | **Adapter-aware results** — `ComputeResult` carries LoRA adapters distinct from full weights; inference composes base+adapter; merge/export is optional | 044, 045 |
| FT-AD-8 | Local fine-tuning targets a **curated small-model catalog** (TinyLlama-class) with known resource envelopes; anything larger routes to SaaS | 041, 044, 046 |
| FT-AD-9 | **Architecture coverage is pedagogical, not exhaustive** — anvil executes a limited model-architecture set; the learning layer explains how architectures differ and why it matters | 044, 049 |
| FT-AD-10 | **Pedagogical progression is first-class** — fine-tuning is an explicit stage in the learning arc; each capability ships with its learning content | 048, 049 |
| FT-AD-11 | **Supported external formats are explicit and fail-closed** — v1 ingests **safetensors only** + Llama-family architectures + HF/SentencePiece tokenizers; everything else is track-but-not-run. **GGUF is a committed but deferred** first-class type (export/import/run/train) split across specs 050–052 | 041, 042, 043, 049; deferred 050, 051, 052 |

---

## The Fine-Tuning Invariant (applies to ALL fine-tuning specs)

The existing product — `pip install anvil && anvil serve`, train a char-level model **from scratch**,
watch it learn, export — is the shipped baseline and the conceptual on-ramp. It MUST remain
behaviorally identical and dependency-light throughout the entire fine-tuning build-out. Two
structural guarantees enforce this (the fine-tuning analogue of the SaaS local-mode invariant):

1. **No heavy deps in the base package.** `torch`, `transformers`, `peft`, `huggingface_hub`,
   `datasets`, and `safetensors`-beyond-export live only in optional extras (`[finetune]`, reusing
   `[gpu]`). `pip install anvil` (no extras) installs none of them. The stdlib training engine
   (`anvil/core/engine.py`) keeps its zero-dependency guarantee.
2. **The from-scratch pretraining path is untouched.** A training run with **no** `base_model_ref`
   is exactly today's pretraining flow. Fine-tuning is strictly additive: a new optional field, new
   backends behind the existing protocol, new services — never a modification of the existing
   pretraining code paths' observable behavior.

### Standard Native-Mode Regression Gate (NMRG)

Every fine-tuning feature's Definition of Done includes ALL of:

```bash
make test            # all pre-existing tests pass UNMODIFIED
make lint            # zero new lint errors
make typecheck       # mypy --strict clean
pip install .        # base install: NO torch / transformers / peft / huggingface_hub pulled in
anvil serve          # boots; from-scratch train → live SSE → export still works end-to-end
```

Plus the **dependency-isolation assertion** (run in CI on every feature):

```bash
python - <<'PY'
import importlib, sys
import anvil.core.engine            # stdlib engine must import with zero ML deps
for forbidden in ("torch", "transformers", "peft", "huggingface_hub", "datasets"):
    assert forbidden not in sys.modules, f"{forbidden} loaded by the stdlib core path"
print("fine-tuning dependency isolation OK")
PY
```

---

## FT-AD-1: Two Fine-Tuning Modes Behind One Compute Seam

**Decision**: anvil supports two conceptually distinct fine-tuning modes, and does not try to force
them through one code path:

- **Native warm-start** — continue training one of anvil's own char-level `LlamaModel` checkpoints
  on new data. Same tokenizer family, same engine, same `LlamaModel`. The engine already supports
  this: `anvil.core.engine.train(docs, model=...)` warm-starts from an existing model.
- **External PEFT** — fine-tune a pretrained HuggingFace model (TinyLlama-class) with LoRA/QLoRA.
  Subword tokenizer, real weights, `transformers`+`peft`, GPU/SaaS-leaning.

Both are submitted through the same `ComputeBackendProtocol` (`anvil/services/compute/`) so the
service/route/registry layers above them are mode-agnostic; only the backend implementation differs.

**Rationale**: The two modes diverge on the two assumptions that matter most — tokenizer (char-level
vs subword) and weight format (anvil `state_dict` vs HF safetensors). Unifying them prematurely
couples the pedagogically-simple native path to the heavyweight external path. Keeping them distinct
lets Track A (native) ship immediately reusing everything, while Track B (external) lands as separate
backends + tokenizer work.

**Gotchas**: The shared seam is the *protocol and result type*, not the engine. Do not leak
`transformers` types above the backend boundary.

## FT-AD-2: Heavy ML Dependencies Are Optional Extras Only

**Decision**: `torch`, `transformers`, `peft`, `huggingface_hub`, `datasets` go in optional extras
(`[finetune]`, composing with the existing `[gpu]`). The base install and the stdlib engine remain
dependency-free. External-model fine-tuning features fail fast with a clear "install
`anvil[finetune]`" message when the extra is absent — mirroring the D4 explicit-capability rule
(`ComputeBackendUnavailable`) already used for the Modal backend.

**Rationale**: The dependency-free stdlib engine is anvil's identity and its conceptual on-ramp.
Pulling multi-hundred-MB ML stacks into every install would betray the "train in seconds, zero deps"
promise. The project already proves this pattern works with `[gpu]` (torch) and `[compute]` (modal).

## FT-AD-3: Tokenizer Abstraction — Tokenizer Travels With the Model

**Decision**: Generalize tokenization so a model carries its tokenizer as a first-class artifact. The
abstraction must hold both anvil's character-level vocabulary (`anvil/core/vocabulary.py`,
`anvil/core/tokenizer.py`) and HuggingFace subword tokenizers. Encode/decode is resolved from the
model's attached tokenizer, never assumed to be char-level.

**Rationale**: External pretrained models are meaningless without their original tokenizer —
character-level encoding would destroy the learned representations. This is the single hardest
assumption the external path breaks, so it is isolated as its own enabling decision/spec (043) that
044 depends on.

**Gotchas**: Export/registry must record which tokenizer family a model uses; downstream inference
and eval must dispatch on it. Spec 008's export already notes the char-level tokenizer is anvil's own
format — extend that record rather than replacing it.

## FT-AD-4: External Models Enter via a Source-Agnostic Import Paradigm

**Decision**: External models are imported through a `ModelSource` abstraction, not hard-wired to
HuggingFace. HF Hub is the first concrete source; local-file/path import is the second. Importing
**creates a tracked metadata entry first** (name, source, architecture family, parameter count,
license, tokenizer family, revision/SHA), and asset download (FT-AD-5) is a separate, explicit step.

**Rationale**: "Support the import-other-models paradigm" is an explicit requirement. A source
interface keeps HF from becoming a hidden dependency of the registry and leaves room for future
sources (a private hub, a URL, a colleague's export). Metadata-before-assets lets users curate and
reason about a model before paying the download/storage cost.

## FT-AD-5: Model Assets Tracked Through Existing Governance; LakeFS Under SaaS

**Decision**: Downloaded model assets (weights, tokenizer files, config) are managed artifacts
tracked by the system, reusing the data-governance and content-store machinery already built for
corpora/datasets. Local mode stores them on the filesystem via the existing `FileStore`; SaaS mode
stores them in **LakeFS** behind the `VersionedContentStore` interface (AD-17, spec 019).

**Rationale**: The user wants downloaded assets "tracked with our system" and "stored in lakeFS when
we support SaaS." Reusing `VersionedContentStore` means versioned, deduplicated, RBAC-scoped model
assets for free, and one storage seam for both corpora and model weights.

**Gotchas**: Model weights are large binaries; ensure content-addressed dedup and signed-URL/stream
access rather than loading into app memory. Respect upstream model licenses recorded at import.

## FT-AD-6: Fine-Tuning Runs Through the Existing Compute Protocol

**Decision**: A fine-tune is a training job that carries a `base_model_ref` plus a `FineTuneSpec`
(method = `full` | `lora` | `qlora`, target modules, rank, etc.). It is dispatched through the
existing `ComputeBackendProtocol`; `anvil/services/compute/resolve.py` selects local vs SaaS by
`ResourceSpec` and base-model size, honoring the D4 degraded-mode rules (auto/local silently fall
back; an explicit SaaS/GPU selection that cannot be honored raises).

**Rationale**: The offload seam already exists (local-stdlib / local-torch / modal, submit-then-poll,
normalized `ComputeResult`). Fine-tuning should be *another job type*, not a parallel pipeline. This
directly satisfies "run a local version, then offload larger workloads to SaaS."

## FT-AD-7: Adapter-Aware Results

**Decision**: Extend `ComputeResult` so a run can return a **LoRA adapter** (small delta) distinct
from full model weights. Inference composes base + adapter at load time; merging the adapter into the
base (producing standalone weights) and exporting is an explicit, optional operation.

**Rationale**: PEFT's value is that the artifact is a small adapter, not a full model copy. The result
type must represent "base + adapter" as a first-class shape so storage, registry, and inference don't
assume monolithic weights. `ComputeResult` already normalizes local-model vs remote-artifact; adapters
are a third shape.

## FT-AD-8: Curated Small-Model Catalog for Local Fine-Tuning

**Decision**: Local fine-tuning targets a **vetted catalog of very small models** (TinyLlama-class)
with documented resource envelopes (params, min RAM/VRAM, supported methods). The catalog gates which
models the local backend offers; larger models are import-able and routable to SaaS but are not
offered for local fine-tuning.

**Rationale**: "Local model support should target very small specific models such as TinyLlama." A
curated catalog gives honest, in-app guidance ("this fits on your machine / this needs SaaS") and
prevents the support nightmare of users OOM-ing on a 7B model locally.

## FT-AD-9: Architecture Coverage Is Pedagogical, Not Exhaustive

**Decision**: anvil executes a deliberately limited set of model architectures (its own Llama-family
primitives plus the curated catalog's families). It does **not** aim to run every architecture.
Instead, the learning layer explains how architectures differ (tokenization, attention variants,
parameter scaling, context length) and what those differences mean in practice.

**Rationale**: "We do not need to support all architectures but we need to cover how architectures
differ, and what this means" in the learning sections. Execution breadth is a cost sink; conceptual
breadth is the product value.

## FT-AD-10: Pedagogical Progression Is First-Class

**Decision**: Fine-tuning is an explicit, ordered stage in the learning arc — a natural progression
from "train from scratch" → "specialize your own model" → "fine-tune a real pretrained model" → "when
to fine-tune vs prompt vs RAG." Each shippable capability ships with the learning content that frames
it; learning specs (048, 049) are first-class deliverables, not documentation afterthoughts.

**Rationale**: anvil's reason for existing is conceptual ramp-up ("an interactive workbench for
understanding how language models actually work"). Fine-tuning must be taught as the next rung of that
ladder, with the same explorable-explanation quality as the existing arc (lineage of Distill.pub).

## FT-AD-11: Supported External Formats Are Explicit and Fail-Closed

**Decision**: anvil enumerates exactly which external formats it accepts and **fails closed** on
everything else — detection happens at import/asset-acquisition time, and an unsupported format is an
explicit, actionable refusal, never a best-effort load. The v1 surface is deliberately small:

- **Weight/serialization format — v1: `safetensors` only.** PyTorch pickle (`.bin`/`.pt`), GGUF, and
  pre-quantized GPTQ/AWQ checkpoints are **rejected** at import with a clear message naming the format
  and pointing to the deferred roadmap (below). Rationale: safetensors carries no arbitrary-code-
  execution risk (unlike pickle), is the HuggingFace default for the curated catalog, and keeps the
  loader surface auditable.
- **Tokenizer serializations — v1:** HF fast tokenizer (`tokenizer.json`) and SentencePiece
  (`tokenizer.model` / `sentencepiece.model`) as used by the Llama family. The serialization type is
  recorded on the model (FT-AD-3).
- **Runnable architecture allow-list — v1: `LlamaForCausalLM`** (Llama 2/3 small variants, TinyLlama).
  Models outside the allow-list are **track-but-not-run**: metadata import works, but fine-tune and
  inference are disabled and the UI links the architecture-differences lesson (049). Mistral and Qwen2
  are named near-term expansion *candidates*, not v1 commitments.

**Provenance**: `safetensors` is already a base dependency (used for export); this decision reuses it
for import. The `architecture family` / `tokenizer family` metadata fields (FT-AD-4) are the
discriminators the detection logic keys on.

**Gotchas**: detect *declared vs actual* format from config + on-disk files (a `.safetensors`
extension is not proof); verify the architecture string against the allow-list before any load attempt;
record the rejection reason on the model entry so the UI can explain it. **Load with
`trust_remote_code` disabled** — only built-in allow-listed architectures execute, so custom remote
modeling code is never fetched or run; a model requiring remote code is track-only.

### Deferred roadmap — GGUF as a first-class type (later priority)

GGUF (the llama.cpp ecosystem format) is a **committed direction but explicitly deferred**, split into
separate shippable specs so each lands independently:

- **050 GGUF Import & Run** — load a GGUF model and run inference on it.
- **051 GGUF Export** — export anvil-trained and merged fine-tuned models to GGUF.
- **052 GGUF Fine-Tuning** — train / fine-tune GGUF-sourced models as first-class.

Until those ship, v1 rejects GGUF per the rule above with a message pointing at this roadmap. GGUF needs
a different runtime than `transformers`/`peft` (llama.cpp / gguf tooling), and quantized-GGUF
fine-tuning is non-trivial — which is precisely why it is deferred rather than crammed into v1. Pickle
formats remain avoided for safety; if ever added, they must be gated behind explicit trust controls.
