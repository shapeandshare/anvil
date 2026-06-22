# Tasks: Llama Engine Evolution & Safetensors Export

**Input**: Design documents from `specs/008-llama-engine-evolution/`
**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/

**Tests**: Test tasks included per spec.md acceptance scenarios and Constitution Article IV (TDD Mandatory).

**Organization**: Tasks grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks within same phase)
- **[Story]**: Which user story this task belongs to (US1, US2, US3)
- Include exact file paths in descriptions

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Add new dependencies required for safetensors export

- [X] T001 Add `safetensors>=0.4` and `numpy>=1.24` to `[project.dependencies]` in pyproject.toml

---

## Phase 2: Foundational — Core Engine Evolution (Blocking Prerequisites)

**Purpose**: Evolve `anvil/core/engine.py` and `anvil/core/autograd.py` from GPT-2 to Llama architecture. **MUST complete before ANY user story.**

**⚠️ CRITICAL**: All user stories depend on these changes being correct. Tests for each change must pass before proceeding.

### SiLU Activation (Value class)

- [X] T002 Add `silu()` method to `Value` class in anvil/core/autograd.py — forward: `x * sigmoid(x)`, backward: `σ(x) + x·σ(x)·(1-σ(x))` as local gradient (FR-004: SiLU activation support)
- [X] T003 Write unit tests for `Value.silu()` in tests/unit/core/test_autograd.py — verify forward value and backward gradient against numerical gradient

### RoPE (Rotary Position Encoding)

- [X] T004 Add `precompute_rope(seq_len, head_dim, theta=10000.0)` function in anvil/core/engine.py — returns `(cos_table, sin_table)` each `[seq_len][head_dim//2]` using `math.cos`/`math.sin`, pure stdlib (FR-003: RoPE). `inv_freq[i] = 1/(theta^(2i/head_dim))` for `i in range(head_dim//2)`
- [X] T005 Add RoPE application as a method on `GPT` class — `apply_rope(q_or_k_vector, position, cos_table, sin_table)` using the **half-split (rotate_half) convention** (FR-003): pair dimension `i` with dimension `i + head_dim/2`, computing `out[i] = x[i]*cos - x[i+h]*sin` and `out[i+h] = x[i+h]*cos + x[i]*sin` where `h = head_dim/2`. ⚠️ MUST NOT use interleaved/consecutive pairing — that silently breaks HF-loaded logits. See research.md §3 for the exact reference implementation
- [X] T006 Wire RoPE into `GPT.forward()`: apply to Q and K after QKV projection, before attention score computation (V is NOT rotated). For the KV cache: rotate each key at its own absolute position EXACTLY ONCE before appending to the cache; never re-rotate cached keys (FR-018)
- [X] T007 Wire RoPE into `GPT.forward_introspect()`: same half-split RoPE application and same cache-rotation discipline for the introspection path
- [X] T008 Remove `wpe` from GPT state dict initialization (line 44 of engine.py) and from forward pass (lines 61-62) (FR-005: remove learned position embeddings)
- [X] T008a Remove the embedding-level RMSNorm from `GPT.forward()` and `GPT.forward_introspect()` (current line 63, the `x = rmsnorm(x)` applied right after the token+position embedding sum). The target architecture has NO embedding-level norm — keeping it breaks equivalence and has no HF tensor to map to (FR-005a)
- [X] T009 Write unit tests for RoPE in tests/unit/core/test_engine.py — verify rotation preserves vector magnitude, position 0 is identity (cos=1, sin=0), different positions produce different rotations, AND verify half-split pairing (dim `i` rotates with dim `i+head_dim/2`, not `i+1`)

### SwiGLU Gated MLP

- [X] T010 Add `intermediate_size = int(8 * n_embd / 3)` computation to `GPT.__init__()` (FR-001: SwiGLU MLP parameter count parity)
- [X] T011 Replace `mlp_fc1`/`mlp_fc2` matrices with `mlp_gate`/`mlp_up`/`mlp_down` matrices in `GPT.__init__()` in anvil/core/engine.py:
  - Remove: `self.state_dict[f"layer{i}.mlp_fc1"] = matrix(4 * n_embd, n_embd)`
  - Remove: `self.state_dict[f"layer{i}.mlp_fc2"] = matrix(n_embd, 4 * n_embd)`
  - Add: `self.state_dict[f"layer{i}.mlp_gate"] = matrix(intermediate_size, n_embd)`
  - Add: `self.state_dict[f"layer{i}.mlp_up"] = matrix(intermediate_size, n_embd)`
  - Add: `self.state_dict[f"layer{i}.mlp_down"] = matrix(n_embd, intermediate_size)`
- [X] T012 Replace ReLU MLP forward pass with SwiGLU in `GPT.forward()` in anvil/core/engine.py:
  - Remove: `x = linear(x, layer{li}.mlp_fc1)` → `x.relu()` → `linear(x, layer{li}.mlp_fc2)`
  - Add: `gate = [xi.silu() for xi in linear(x, layer{li}.mlp_gate)]` → element-wise multiply with `up = linear(x, layer{li}.mlp_up)` → `linear([g*u for g,u in zip(gate, up)], layer{li}.mlp_down)`
  - ⚠️ `gate_proj` is the SiLU-activated branch, `up_proj` is the linear branch — do NOT swap (swapping loads cleanly but produces wrong output)
- [X] T013 Apply same SwiGLU replacement in `GPT.forward_introspect()` in anvil/core/engine.py
- [X] T014 Write unit tests for SwiGLU in tests/unit/core/test_engine.py — verify parameter count parity with old ReLU MLP (~8n²), verify forward produces valid output, verify gradient flow

### Learned RMSNorm Scale Parameters

- [X] T015 Add `rms_1` (pre-attention) and `rms_2` (pre-MLP) learned scale parameters to `GPT.__init__()` — each is a list of `n_embd` Value objects initialized to 1.0 (Value(1.0, ...)) (FR-002: learned RMSNorm weights)
- [X] T016 Add `rms_final` learned scale parameter to `GPT.__init__()` — applied before lm_head
- [X] T017 Update `GPT.forward()` to apply learned scales: `x = [r * xi for r, xi in zip(rms_weights, rmsnorm(x))]` at pre-attention, pre-MLP, and pre-lm_head norm points
- [X] T018 Update `GPT.forward_introspect()` with same learned scale application
- [X] T019 Write unit tests for learned RMSNorm in tests/unit/core/test_engine.py — verify scale initializes to 1.0, verify gradient flows through scale parameters

### Save/Load Format Update

- [X] T020 Update `GPT.save()` in anvil/core/engine.py to include `intermediate_size` in JSON output and exclude `wpe`/`fc1`/`fc2` keys — serializes new state dict only (FR-010: secondary JSON format updated)
- [X] T021 Update `GPT.load()` in anvil/core/engine.py to (FR-011: old format detection with clear error):
  - Read `intermediate_size` if present (new format)
  - Detect old format by checking for `wpe` key — raise `ValueError("Model format is incompatible: this checkpoint uses the GPT-2 architecture (wpe, fc1/fc2). The current engine uses Llama architecture (RoPE, SwiGLU). Retrain with the current version.")`
- [X] T022 Write unit tests for save/load format detection in tests/unit/core/test_engine.py — verify old format raises clear error, verify new format round-trips correctly

### `params` list update

- [X] T023 Update `GPT.params` property to include new parameters (rms_1, rms_2, rms_final, mlp_gate, mlp_up, mlp_down) and exclude removed ones (wpe, mlp_fc1, mlp_fc2)

### Config Validation

- [X] T023a Add head_dim-even validation in `GPT.__init__()` (and/or training config validation) — require `n_embd % (2 * n_head) == 0` so `head_dim` is an even integer. Raise a clear `ValueError` for odd head_dim (e.g., n_embd=30, n_head=6 → head_dim=5), since RoPE requires even head_dim (FR-017)
- [X] T023b Write unit tests in tests/unit/core/test_engine.py for head_dim validation — verify odd head_dim configs raise clear error, valid configs pass

**Checkpoint**: Core engine is Llama-compatible. `python -c "from anvil.core.engine import GPT; g=GPT(27); print(g.num_params())"` works. Unit tests pass. Old model.json loading fails with clear error.

---

## Phase 3: User Story 1 — Train a Llama-Compatible Model (Priority: P1) 🎯 MVP

**Goal**: A user trains a model on their own dataset. When training completes, the model is automatically serialized to safetensors as the primary artifact with standards-compatible config and tokenizer.

**Independent Test**: Train a minimal model (n_embd=16, n_layer=1, n_head=4) on a small corpus, verify safetensors file + config.json + tokenizer.json are produced, and verify the exported model loads without errors.

### Tests for User Story 1

- [X] T024 [P] [US1] Write unit test for safetensors export function in tests/unit/services/test_export.py — verify tensor mapping (anvil keys → HF keys), dtype (float32), shape correctness, AND that NO synthetic tensors are injected (FR-009: every tensor must correspond to a trained parameter)
- [X] T025 [P] [US1] Write unit test for config.json generation in tests/unit/services/test_export.py — verify all LlamaConfig fields present with correct mapping from hyperparams, including `rope_theta=10000.0`, `rope_scaling=null`, `hidden_act="silu"`, `tie_word_embeddings=false`, `attention_bias=false`, `mlp_bias=false`
- [X] T026 [P] [US1] Write unit test for tokenizer file generation in tests/unit/services/test_export.py — verify character vocabulary serialized correctly in the platform's own format (NOT claimed to be a standard auto-loadable tokenizer)
- [X] T027 [P] [US1] Write integration test in tests/integration/test_training.py — train model, verify safetensors export runs on completion. Then: (a) load exported safetensors with `safetensors.safe_open()` and verify ALL expected HF-convention keys are present (embed_tokens, q/k/v/o_proj, gate/up/down_proj, input_layernorm, post_attention_layernorm, model.norm, lm_head — and NO bias keys); (b) load exported config.json with `json.load()` and validate required LlamaConfig fields (SC-003); (c) compute a native reference forward pass IN FLOAT32 (same precision as export) and verify exported-vs-native logits match within rtol=1e-4, atol=1e-4 across 10 random input sequences, AND argmax (token-level) agreement is exact (SC-002)
- [X] T027a [P] [US1] Write a golden cross-implementation test in tests/integration/test_export_golden.py — for a tiny model (n_embd=8, n_head=2, n_layer=1), compare native anvil intermediate tensors against a reference Llama forward pass: q, k, rotated q/k (verify half-split RoPE matches), attention scores, and final logits. This catches silent RoPE-convention, norm-structure, layout-transpose, and SwiGLU-branch-swap bugs. If `transformers`/`torch` unavailable in the test env, skip with a clear marker

### Implementation for User Story 1

#### Engine ↔ Service Bridge

- [X] T028 [US1] Add `intermediate_size` as a public attribute on `GPT` class in anvil/core/engine.py (already computed in __init__; expose as `self.intermediate_size`)
- [X] T029 [P] [US1] Add `export_state_dict(model: GPT) -> dict` helper function in `anvil/services/export.py` (will be created in T030) — maps internal state dict keys (wte, layer{i}.attn_wq, layer{i}.mlp_gate, etc.) to HuggingFace-compatible names (model.embed_tokens.weight, model.layers.{i}.self_attn.q_proj.weight, model.layers.{i}.mlp.gate_proj.weight, etc.) as 2D list-of-lists. This is a pure data transformation — no numpy, no safetensors import needed yet

#### Safetensors Export Service

- [X] T030 [P] [US1] Create `anvil/services/export.py` with `SafetensorsExportService` class:
  - `export_to_safetensors(model: GPT, output_dir: str, chars: list[str]) -> dict` — converts internal state dict lists to `np.float32` contiguous arrays, writes with `safetensors.numpy.save_file()`. Namespace mapping uses `export_state_dict()` from T029. On import failure (safetensors or numpy not installed), raises clear error: "safetensors export requires 'safetensors' and 'numpy' packages. Install with: pip install safetensors numpy"
  - `generate_config(model: GPT) -> dict` — returns LlamaConfig-compatible JSON dict
  - `generate_tokenizer(chars: list[str]) -> dict` — returns character vocabulary JSON
  - `retry_export(model_path: str, output_dir: str) -> dict` — load existing model.json and retry safetensors generation
- [X] T031 [US1] Wire `SafetensorsExportService` into `TrainingService.start_training()` in anvil/services/training.py — call export automatically on successful training completion via the `on_complete` callback. On export failure: (a) training run is STILL recorded as successful (loss is valid); (b) write a warning log with the error details; (c) emit an error event in the SSE metrics stream so the UI can display a prominent failure banner; (d) store the error metadata so the user can retry export later (FR-016)

#### GPU Backend Update (REQUIRED — not optional)

> ⚠️ The GPU backend is NOT out of scope. `TrainingService.start_training()` bridges GPU-trained weights into the canonical CPU `GPT` representation via `_load_weights_into_model()` (keyed by state dict name). If the GPU path stays on the old GPT-2 architecture while the CPU engine becomes Llama, the keys won't match and export + inference break (FR-019).

- [X] T032 [US1] Update `anvil/core/torch_engine.py` (`TorchGPT` class) to match Llama architecture (FR-019): remove `wpe`, add SwiGLU (gate/up/down with `F.silu`), add learned RMSNorm weights (rms_1, rms_2, rms_final via `F.rms_norm` with learnable weight then scale, or manual), apply half-split RoPE to Q/K, remove embedding-level norm, add final norm before lm_head. Update `export_weights()` to emit the new state dict keys (no wpe/fc1/fc2; include rms_1/rms_2/rms_final/mlp_gate/mlp_up/mlp_down)
- [X] T033 [US1] Update `_load_weights_into_model()` in anvil/services/training.py to handle new state dict keys (rms_1/rms_2/rms_final are 1D vectors, not 2D matrices — handle the shape difference when copying values)

#### Demo Model Auto-Retrain

- [X] T034 [US1] Update `_train_demo_model()` in anvil/services/inference.py — train with new Llama architecture, save in new format (FR-012: demo model auto-retrain on format mismatch)
- [X] T035 [US1] Update `DemoModelProvider.get_model()` in anvil/services/inference.py — detect old format on load failure and trigger auto-retrain (FR-012)

#### Inference Service Updates

- [X] T036 [US1] Update the following methods in `anvil/services/inference.py` to reference new state dict keys (SwiGLU gate/up/down instead of fc1/fc2, no wpe, learned rms_1/rms_2 weights): `embeddings()` — remove wpe from embedding visualization; `attention()` — add RoPE angle display alongside attention weights; `model_params()` — update parameter grouping for SwiGLU projections (gate/up/down) and RMSNorm scales
- [X] T037 [US1] Update inference API endpoints in `anvil/api/v1/inference.py` if they pass architecture-specific data to widgets

#### MLflow Tracking

- [X] T038 [US1] Update tracking in `anvil/services/tracking.py` (or related tracking service) to log safetensors file as primary artifact and model.json as secondary artifact on training completion (FR-008: store, track, version safetensors artifacts)
- [X] T039 [US1] Update `on_complete` callback wiring to pass safetensors paths to MLflow artifact logging

**Checkpoint**: Train a model end-to-end. Safetensors checkpoint + config + tokenizer are auto-generated. Exported model loads in HF-compatible tool. Old format fails gracefully.

---

## Phase 4: User Story 2 — Learn the Llama Architecture Through Walkthroughs (Priority: P2)

**Goal**: A student progresses through the six training walkthroughs, each teaching one component of the Llama architecture, culminating in a full modern decoder-only transformer.

**Independent Test**: Run each walkthrough script from train0.py to train5.py sequentially. Each produces the expected model components and loss behavior. The train5 export produces a valid safetensors checkpoint.

### Implementation for User Story 2

- [X] T040 [P] [US2] Update `examples/train0.py` — single neuron with sigmoid (unchanged concept, verify it still works cleanly) (FR-015: walkthrough progression)
- [X] T041 [P] [US2] Update `examples/train1.py` — linear layer with matrix multiply and analytic gradient verification (unchanged concept, verify)
- [X] T042 [P] [US2] Update `examples/train2.py` — RMSNorm with learned weights (introduce `rmsnorm()` with scale parameter `rms_1` initialized to 1.0, backpropagation through normalization with Adam)
- [X] T043 [P] [US2] Update `examples/train3.py` — self-attention with RoPE (learned wte + RoPE applied to Q/K, causal self-attention, no MLP, no wpe, train on bigram data)
- [X] T044 [P] [US2] Update `examples/train4.py` — transformer block with SwiGLU (full block: pre-attn RMSNorm + RoPE attention → residual → pre-MLP RMSNorm + SwiGLU MLP → residual, single layer, train on bigram data)
- [X] T045 [P] [US2] Update `examples/train5.py` — full Llama-aligned GPT (multi-layer GPT using the engine, Adam optimizer, complete training loop, safetensors export demonstration)

**Checkpoint**: All six walkthrough scripts execute without errors. Each produces a valid model with correct architecture components for that lesson. Train5 produces a safetensors checkpoint.

---

## Phase 5: User Story 3 — Access and Share Trained Models (Priority: P3)

**Goal**: An engineer accesses their trained models through the experiment tracking interface. Safetensors checkpoints are stored, tracked, and versioned. They can download, re-export, or share.

**Independent Test**: Train a model, verify the safetensors checkpoint appears in the experiment tracking UI with correct metadata. Download the checkpoint and load it in an external tool.

### Implementation for User Story 3

- [X] T046 [P] [US3] Update experiment tracking UI templates (anvil/api/templates/) to display safetensors artifact info (path, size, tensor count) alongside training results
- [X] T047 [P] [US3] Add API endpoint in `anvil/api/v1/experiments.py` to download safetensors checkpoint by experiment/run ID
- [X] T048 [P] [US3] Add API endpoint to retry safetensors export from existing model.json for a completed run
- [X] T049 [US3] Integrate safetensors artifact listing into the tracking service — query MLflow for safetensors artifacts per run, return in consistent format
- [X] T050 [US3] Add `architectures` field to experiment metadata in MLflow — record that model uses `LlamaForCausalLM` architecture

**Checkpoint**: Trained models appear in experiment tracking with safetensors artifact listed. User can download and retry export. The architecture type is recorded.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories

- [X] T051 [P] Update forward introspection widget in `anvil/services/inference.py` — trace attention weights through RoPE flow (show cos/sin values at each position for the active head)
- [X] T052 [P] Update model params widget — display new state dict groups (embedding, attention projections, SwiGLU MLP projections, RMSNorm scales, output)
- [X] T053 [P] Update e2e tests in `tests/e2e/test_inference_widgets.py` — update expected state dict keys, add tests for new architecture components
- [X] T054 [P] Update unit tests for `anvil/core/engine.py` in `tests/unit/core/test_engine.py` — add comprehensive tests for all new architecture components and edge cases:
  - n_layer=0 (embedding → lm_head only, valid single-layer model — spec edge case)
  - n_embd=4, n_head=2 (tiny dimensions — RoPE edge case, spec edge case)
  - n_embd=16, n_head=4, n_layer=1 (standard config — SC-001 baseline)
  - Verify training produces valid loss and state dict matches expected keys
- [X] T055 Run full test suite — `make test`, `make lint`, `make typecheck` — fix issues found. Also do a manual smoke test: train a minimal model (n_embd=16, n_layer=1, n_head=4, num_steps=400) on the demo corpus and verify it completes in under 60 seconds (SC-001)
- [X] T056 [P] Update AGENTS.md and docs/vault/ with new architecture information (RoPE, SwiGLU, safetensors export)
- [X] T057 [P] Write ADR for Llama engine evolution if not already recorded in docs/vault/Decisions/

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately
- **Foundational (Phase 2)**: Depends on Setup — **BLOCKS all user stories**
- **User Stories (Phase 3-5)**: All depend on Foundational completion
  - US1 → US3: US3 depends on US1 (safetensors export must work before tracking/download)
  - US2: Independent of US1/US3 (walkthroughs use core engine which is complete in Phase 2)
- **Polish (Phase 6)**: Depends on all user stories

### User Story Dependencies

- **US1 (P1)**: Phase 2 complete → MVP scope
- **US2 (P2)**: Phase 2 complete only — independent of US1
- **US3 (P3)**: Phase 2 + US1 complete (depends on safetensors export existing)

### Within Each Phase

- Core engine changes (engine.py) before service layer changes
- Tests written before implementation (TDD per Constitution)
- Services before API endpoints
- Core before UI

### Parallel Opportunities

- **Phase 2**: T002+T004+T010 can be designed independently (SiLU, RoPE, SwiGLU are separate concerns), but all converge on engine.py — implement sequentially to avoid merge conflicts
- **Phase 3**: T024-T027 (tests) can run after T028-T031 (implementation). T030 (export service) independent of T032 (torch_engine)
- **Phase 4**: T040-T045 — all walkthroughs are independent files, can be updated in parallel
- **Phase 6**: T051-T057 — all independent, can run in parallel

---

## Parallel Example: Phase 4 — Walkthrough Updates

```bash
# All walkthrough updates are independent — fire simultaneously:
Task: "Update train0.py in examples/train0.py — single neuron (unchanged)"
Task: "Update train1.py in examples/train1.py — linear layer (unchanged)"
Task: "Update train2.py in examples/train2.py — RMSNorm with learned weights"
Task: "Update train3.py in examples/train3.py — self-attention with RoPE"
Task: "Update train4.py in examples/train4.py — SwiGLU transformer block"
Task: "Update train5.py in examples/train5.py — full Llama GPT with export"
```

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (add safetensors dep)
2. Complete Phase 2: Foundational (core engine — BLOCKS everything)
3. Complete Phase 3: User Story 1 (training + export)
4. **STOP and VALIDATE**: Train a model end-to-end, verify safetensors export
5. Deploy/demo if ready

### Incremental Delivery

1. **Phase 1 + Phase 2** → Core engine evolved to Llama architecture
2. **Phase 3 (US1)** → Training produces safetensors checkpoints — MVP deliverable
3. **Phase 4 (US2)** → Walkthroughs teach the new architecture
4. **Phase 5 (US3)** → Tracking, downloads, sharing
5. **Phase 6 (Polish)** → Widget updates, tests, docs

### Parallel Team Strategy

1. Complete Phase 1 + Phase 2 together (foundation is critical)
2. Once foundation is done:
   - **Team A**: Phase 3 (US1) — export service, training wiring, GPU backend
   - **Team B**: Phase 4 (US2) — walkthrough updates (all 6 files independent)
3. Phase 5 + 6 after US1 is stable

---

## Notes

- [P] tasks = different files, no dependencies on incomplete sibling tasks
- [Story] label maps task to specific user story for traceability
- Each user story phase is independently completable and testable
- Write tests before implementation (TDD per Constitution Article IV)
- Commit after each task or logical group
- Stop at any checkpoint to validate independently