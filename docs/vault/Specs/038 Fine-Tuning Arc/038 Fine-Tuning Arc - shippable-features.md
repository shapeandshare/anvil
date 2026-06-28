---
title: 038 Fine-Tuning Arc - shippable-features
type: spec
tags:
  - type/spec
  - domain/training
  - domain/learning
status: draft
spec-refs:
  - docs/vault/Specs/038 Fine-Tuning Arc/
related:
  - '[[038 Fine-Tuning Arc]]'
  - '[[Reference/FineTuningArchitectureDecisions]]'
created: '2026-06-28'
updated: '2026-06-28'
---
# Shippable Feature Breakdown: Fine-Tuning Arc

This decomposes the umbrella spec (`038 Fine-Tuning Arc - spec.md`) into **discrete, independently
shippable features** — child specs **039–049** — ordered by dependency and value delivery. Each one
delivers user-visible value on its own and can be developed, tested, and demonstrated independently.

> **Hard constraint — the from-scratch experience never breaks.** Every feature carries the
> **Native-Mode Regression Gate (NMRG)** in its Definition of Done. This is the fine-tuning analogue
> of the SaaS local-mode invariant. See [[Reference/FineTuningArchitectureDecisions|FT-AD-1..10]]
> (FT-AD-2 and the Fine-Tuning Invariant section).

## The Fine-Tuning Invariant (applies to ALL features)

The shipped product — `pip install anvil && anvil serve`, train a char-level model from scratch, watch
it learn, export — is the baseline and the conceptual on-ramp. It MUST remain behaviorally identical
and dependency-light throughout. Two structural guarantees:

1. **No heavy deps in the base package** — `torch`, `transformers`, `peft`, `huggingface_hub`,
   `datasets` live only in optional extras (`[finetune]`, composing with `[gpu]`). `pip install anvil`
   installs none of them; `anvil/core/engine.py` keeps its zero-dependency guarantee.
2. **The from-scratch path is untouched** — a run with no `base_model_ref` is exactly today's
   pretraining flow. Fine-tuning is strictly additive.

### Standard Native-Mode Regression Gate (NMRG)

Every feature's Definition of Done includes ALL of:

```bash
make test            # all pre-existing tests pass UNMODIFIED
make lint            # zero new lint errors
make typecheck       # mypy --strict clean
pip install .        # base install: NO torch / transformers / peft / huggingface_hub pulled in
anvil serve          # boots; from-scratch train → live SSE → export still works end-to-end
```

Plus the **dependency-isolation assertion** (CI, every feature):

```bash
python - <<'PY'
import sys, anvil.core.engine
for forbidden in ("torch", "transformers", "peft", "huggingface_hub", "datasets"):
    assert forbidden not in sys.modules, f"{forbidden} loaded by the stdlib core path"
print("fine-tuning dependency isolation OK")
PY
```

---

## Delivery Tracks

| Track | Specs | Theme |
|-------|-------|-------|
| **A — Native fine-tuning** | 039 | Specialize anvil's own models (reuses everything) |
| **B foundation — import** | 040, 041, 042 | Bring external models into the system + assets |
| **B core — local PEFT** | 043, 044, 045 | Subword tokenizer, LoRA engine, adapter inference |
| **Offload** | 046, 047 | Compute routing + SaaS fine-tuning pipeline |
| **Pedagogy** | 048, 049 | First-class learning content |

**Recommended order**: 039 → 048 (concepts) → 040 → 041 → 042 → 043 → 053 (dataset prep) → 044 → 045 →
054 (eval) → 055 (teaching loop) → 049 → 046 → 047.
039 ships first (smallest, highest reuse). The two learning specs (048, 049) are intentionally placed
early/mid so concepts land with the capabilities they frame (FT-AD-10), not after.

---

## Feature 039 — Native Warm-Start & Run Lineage

**Owns**: FR-001..FR-004 · **Track**: A · **Owned decisions**: FT-AD-1 (native side)

**Ships**: optional `base_model_ref` on a training run; warm-start wiring through the training service;
the `train_torch` warm-start fix (add `model=` parity with the stdlib engine); lineage recorded in the
model registry (parent ref + specialization corpus); UI affordance to "continue training / specialize"
a registered model.

**Value**: A learner specializes a model they already trained and watches it adapt — the first, fully
native taste of fine-tuning, with **zero new dependencies**.

**Risk to the invariant: LOW.** Additive field + new engine code path. The no-base path is unchanged.
The one care point is the `torch_engine` change — guard it behind the existing `[gpu]` extra and keep
the stdlib warm-start as the reference behavior.

**Definition of Done**: lineage visible in the registry; warm-start measurably starts below a
from-scratch run; **NMRG (full)**; a run with no base model is byte-for-byte today's behavior (FR-027).

---

## Feature 040 — External Model Registry & Import Paradigm

**Owns**: FR-005, FR-006, FR-009 · **Track**: B foundation · **Owned decisions**: FT-AD-4

**Ships**: the `ModelSource` abstraction (HF Hub + local-file sources); `ExternalModel` metadata entity
+ repository; registry extension (spec 003) to track external models alongside anvil's own, with origin;
"import" action creating a metadata-only entry (no assets yet); generic local-file import path.

**Value**: Users can bring any supported external model into anvil as a tracked, curated entry — the
foundation every later external-model feature builds on.

**Risk to the invariant: LOW.** All new modules; `huggingface_hub` behind the `[finetune]` extra and
only touched when a source is actually queried.

**Definition of Done**: import creates a complete metadata entry (FR-006 fields) before download;
source abstraction has ≥2 implementations (HF, local); **NMRG (full)**.

---

## Feature 041 — HuggingFace Model Browser & Curated Catalog

**Owns**: FR-007, FR-008, FR-032 (publish allow-list) · **Track**: B foundation · **Owned decisions**: FT-AD-8, FT-AD-11 (allow-list aspect)

**Ships**: in-app HF view (search, browse, inspect model cards via HF Hub API); the curated
small-model catalog (TinyLlama-class) with documented resource envelopes; per-model local-eligibility
flag; one-click import that feeds Feature 040.

**Value**: A guided, in-app way to discover models that will actually fit the learner's machine — no
leaving the app, no guessing whether a model is too big.

**Risk to the invariant: LOW.** New UI + read-only HF API calls behind the extra.

**Definition of Done**: search→inspect→import works for a catalog model; each model shows
local-eligibility from its envelope; **NMRG (full)**.

---

## Feature 042 — Model Asset Acquisition & Storage (LakeFS-ready)

**Owns**: FR-010..FR-013, FR-030 (weight formats), FR-033 (format detection / fail-closed) · **Track**: B foundation · **Owned decisions**: FT-AD-5, FT-AD-11 (format aspect)

**Ships**: asset download (weights/tokenizer/config) for an imported model; managed content-addressed
storage via the existing `FileStore` (local) and `VersionedContentStore`/LakeFS (SaaS, AD-17);
idempotent/resumable download + checksums; license recording/enforcement; metadata flips to "assets
available".

**Value**: External models become *usable* — their assets are present and tracked the same way corpora
and datasets are, and SaaS storage is org-scoped in LakeFS.

**Risk to the invariant: LOW–MEDIUM.** Reuses the storage seam; care that large binaries stream rather
than load into memory and that LakeFS pathing matches spec 019.

**Definition of Done**: download → tracked, checksummed assets; SaaS mode writes through
`VersionedContentStore`; interrupted download resumes cleanly; **NMRG (full)**.

---

## Feature 043 — Subword Tokenizer Abstraction

**Owns**: FR-014, FR-015, FR-031 (tokenizer serializations) · **Track**: B core · **Owned decisions**: FT-AD-3, FT-AD-11 (tokenizer aspect)

**Ships**: tokenizer abstraction where a model carries its tokenizer as a first-class artifact;
char-level (existing `anvil/core/vocabulary.py`/`tokenizer.py`) and HF subword implementations;
encode/decode dispatch from the attached tokenizer; tokenizer-family recorded on the model for
inference/eval.

**Value**: The enabling layer that lets external models be tokenized correctly — the single hardest
assumption the external path breaks. Independently testable via round-trip encode/decode parity for
both families.

**Risk to the invariant: MEDIUM.** Touches the tokenization seam used by the existing char-level path.
Contract tests must prove char-level behavior is identical post-abstraction (parallels the 028 "slide
existing impls behind interfaces" risk).

**Definition of Done**: both tokenizer families round-trip; existing char-level training/inference
unchanged under contract tests; **NMRG (full)**.

---

## Feature 044 — Local LoRA/QLoRA Fine-Tuning Engine (TinyLlama-class)

**Owns**: FR-016..FR-019 · **Track**: B core · **Owned decisions**: FT-AD-1 (external side), FT-AD-9 (exec scope)
· **Depends on**: 042 (assets), 043 (tokenizer)

**Ships**: a `transformers`+`peft` fine-tuning backend registered behind `ComputeBackendProtocol`;
`FineTuneSpec` (method `full`/`lora`/`qlora`, target modules, rank/alpha, quantization, LR, steps);
local resource-envelope gating (route-or-guide beyond catalog limits); fail-fast `[finetune]` extra
probe; live metrics through the existing pipeline.

**Value**: The headline capability — fine-tune a real pretrained model locally and get a small adapter.

**Risk to the invariant: LOW.** New backend behind the existing protocol and the optional extra; no
existing path modified. Real risk is *capability/UX* (OOM avoidance), handled by envelope gating.

**Definition of Done**: a catalog model LoRA-fine-tunes locally with its subword tokenizer, producing a
tracked adapter; missing extra fails fast with an install hint; over-envelope attempts guide to SaaS;
**NMRG (full)**.

---

## Feature 045 — Adapter Inference, Merge & Export

**Owns**: FR-020, FR-021 · **Track**: B core · **Owned decisions**: FT-AD-7 · **Depends on**: 044

**Ships**: `ComputeResult` extended to carry an adapter as a first-class shape; inference that composes
base+adapter at load time (extends the inference service); optional adapter→standalone-weights merge
and export + registration.

**Value**: Closes the loop — a fine-tuned model can be run, taken away, and shared.

**Risk to the invariant: LOW.** Additive result shape and inference path.

**Definition of Done**: base+adapter generates fine-tuned samples; merge+export yields a standalone
artifact that runs without the adapter; **NMRG (full)**.

---

## Feature 046 — Fine-Tune Compute Routing & Adapter Results

**Owns**: FR-022 · **Track**: Offload · **Owned decisions**: FT-AD-6 · **Depends on**: 044, 045

**Ships**: fine-tune as a first-class job type in the compute layer; `ResourceSpec`-based sizing for
fine-tunes; `resolve.py` routing of local vs SaaS by base-model size under D4 (auto/local fall back;
explicit-unavailable raises); adapter-aware result normalization across local and remote.

**Value**: One consistent path — the same fine-tune config runs locally or offloads, decided by size,
not by a separate workflow.

**Risk to the invariant: LOW.** Extends the existing resolution/registry layer; no native path change.

**Definition of Done**: a fine-tune routes to the correct backend by size; D4 semantics honored;
adapter results normalize identically local vs remote; **NMRG (full)**.

---

## Feature 047 — SaaS Fine-Tuning Pipeline

**Owns**: FR-023 · **Track**: Offload · **Depends on**: 046, plus spec 032 (SaaS training pipeline), 019 (LakeFS)

**Ships**: SaaS-side fine-tune execution on the existing Batch GPU pipeline (spec 032) — base assets
fetched from LakeFS, PEFT run on GPU, durable `job_events`, SSE/poll metrics, usage metering; adapter
artifact stored in LakeFS and registered, org-scoped.

**Value**: Larger fine-tunes that won't fit locally run in SaaS with the same live experience and
governance as SaaS training.

**Risk to the invariant: LOW.** SaaS-only path behind the SaaS entrypoint; local mode unaffected (it
inherits the SaaS specs' local-mode invariant too).

**Definition of Done**: an over-local fine-tune runs on SaaS, streams metrics, and returns a tracked,
org-scoped adapter from LakeFS; metering records usage; **NMRG (full)** for local.

---

## Feature 048 — Learning Arc: Fine-Tuning Concepts

**Owns**: FR-024, FR-026 · **Track**: Pedagogy · **Owned decisions**: FT-AD-10

**Ships**: explorable learning pages — what fine-tuning is; warm-start vs PEFT/LoRA (with LoRA
intuition); when to fine-tune vs prompt vs RAG — wired into the existing learning navigation as an
ordered progression from the from-scratch material.

**Value**: Learners understand *why* and *when*, not just *how* — the conceptual ramp that is anvil's
reason for existing.

**Risk to the invariant: NONE.** Content + UI only.

**Definition of Done**: pages exist in the explorable-explanation style, linked as a progression;
**NMRG (full)**.

---

## Feature 049 — Learning Arc: Architecture Differences

**Owns**: FR-025, FR-026, FR-032 (allow-list lesson) · **Track**: Pedagogy · **Owned decisions**: FT-AD-9, FT-AD-10, FT-AD-11 (allow-list aspect)

**Ships**: an architecture-differences module — tokenization, attention variants, parameter scaling,
context length — and what each implies for fine-tuning; explicit framing that anvil executes a limited
architecture set while teaching the broader landscape; contrasts anvil's char-level mini-Llama with
TinyLlama-class and larger families.

**Value**: Learners grasp how the model zoo differs and why anvil supports some but not all — turning a
scoping limitation into a teaching moment.

**Risk to the invariant: NONE.** Content + UI only.

**Definition of Done**: module explains differences and implications without claiming exhaustive
execution support; cross-linked from the catalog's "not eligible / unknown architecture" flags;
**NMRG (full)**.

---

---

## Workflow Completeness (053–055)

These close usability gaps the core arc assumes. They are v1-tier (not deferred) and interleave with the
arc rather than following it.

## Feature 053 — Fine-Tuning Dataset Preparation

**Owns**: FR-034 · **Track**: B core (enabler, before 044) · **Decisions**: reuses FT-AD-3, FT-AD-5

**Ships**: SFT prompt→response formatting; base-model chat-template application; optional
chosen/rejected preference pairs; all tracked via the datasets governance (005) and consumable by
044/047 unchanged.

**Value**: Makes instruction fine-tuning actually usable — raw examples become correctly formatted,
chat-templated training data. **Risk: LOW.** **DoD**: raw → tracked SFT dataset with template recorded;
**NMRG (full)**.

## Feature 054 — Fine-Tuned Model Evaluation

**Owns**: FR-035 · **Track**: Evaluation (after 045) · **Decisions**: reuses FT-AD-7, FT-AD-10

**Ships**: side-by-side base-vs-fine-tuned sample comparison + quantitative metrics + recorded
base→fine-tuned delta, reusing the eval service; adapter + tokenizer-family aware.

**Value**: Answers "did it help?" for warm-start and adapter models. **Risk: LOW.** **DoD**: side-by-side
+ metric delta recorded; `track-only` refused; **NMRG (full)**.

## Feature 055 — Interactive Teaching Loop

**Owns**: FR-036 · **Track**: Pedagogy/workflow (after 039 + 053) · **Decisions**: FT-AD-10; reuses FT-AD-1

**Ships**: an iterative add-examples→short-fine-tune→inspect→repeat loop, each round checkpoint-chained
(warm-start) with visible session lineage, rollback/branch, and native+adapter support; composes 039,
053, 045, 054.

**Value**: Realizes the "teach it" goal — fine-tuning that feels like teaching, not a one-shot job.
**Risk: LOW** (orchestration over existing capabilities). **DoD**: ≥2 chained rounds with lineage +
rollback; **NMRG (full)**.

---

## Deferred / Later — GGUF First-Class Support (050–052)

GGUF (the llama.cpp ecosystem format) is a **committed direction but explicitly deferred** (FT-AD-11).
v1 rejects GGUF on import; these three specs make it first-class, each independently shippable. They are
sequenced **after** the v1 arc (039–049) and are not required for any v1 success criterion.

- **050 GGUF Import & Run** — load a GGUF model and run inference (separate runtime from
  `transformers`/`peft`).
- **051 GGUF Export** — export anvil-trained and merged fine-tuned models to GGUF (consumes 045's
  merge/export).
- **052 GGUF Fine-Tuning** — train / fine-tune GGUF-sourced models as first-class (depends on 050 + 044).

Until they ship, FR-030 keeps the boundary honest: GGUF is refused with a message pointing at this
roadmap.

## Dependency Summary

```
039 (native warm-start) ─────────────────────────────► ships first, standalone
040 (import) ─► 041 (HF browser) ─► 042 (assets) ─┐
043 (tokenizer) ──────────────────────────────────┤
                                                   ▼
                                          044 (local LoRA) ─► 045 (adapter infer/export)
                                                   │
                                                   ▼
                                          046 (routing) ─► 047 (SaaS pipeline)  [needs 032, 019]
048 (concepts)  — early/mid, frames 039–044
049 (architectures) — mid, frames 044/041 eligibility
```
