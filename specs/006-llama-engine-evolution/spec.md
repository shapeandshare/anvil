# Feature Specification: anvil — Llama Engine Evolution & Safetensors Export

**Feature Branch**: `006-llama-engine-evolution`  
**Created**: 2026-06-14  
**Status**: Draft  
**Project**: anvil  
**Input**: User description: "Evolve the anvil core training engine to a Llama-compatible architecture. Replace ReLU MLP with SwiGLU, add learned RMSNorm weights, replace learned position embeddings with RoPE. The safetensors format is the primary model delivery artifact — generated, stored, tracked, and versioned automatically."

## Clarifications

### Session 2026-06-14

- Q: How should the safetensors export be triggered relative to training? → A: Automatic first-class artifact — safetensors is the primary model delivery mechanism, generated automatically on every training completion, stored, tracked, and versioned. The native JSON is a secondary/internal representation.
- Q: What should happen when safetensors generation fails during training completion? → A: Training is still considered successful (loss is valid), but the failure is prominently flagged in the UI/logs. The user can retry generation later from the native JSON.
- Q: What does "versioned" mean operationally for safetensors checkpoints? → A: One immutable version per training run, keyed by experiment/run ID. Re-training produces a new version. No manual semantic version labeling.
- Q: Which RoPE pairing convention should the engine use? → A: The half-split (rotate_half) convention used by the target decoder-only architecture — dimension `i` is paired with dimension `i + head_dim/2`. The engine MUST train and run inference using this same convention so exported weights load without permutation. (Interleaved/consecutive pairing is explicitly rejected — it would silently produce mismatched logits when loaded by a standards-compatible tool.)
- Q: What is the correct normalization structure? → A: Pre-attention norm (per layer), pre-MLP norm (per layer), and a single final norm before the output projection. There is NO embedding-level normalization. The previous engine's embedding-level norm MUST be removed — it has no corresponding tensor in the target architecture.
- Q: What is the forward-pass logit tolerance for verifying export fidelity? → A: The native reference forward pass MUST be computed in the same float precision as the exported artifact (float32). Logit agreement is verified with relative tolerance 1e-4 and absolute tolerance 1e-4; token-level (argmax) agreement is verified separately. The previously stated 1e-5 tolerance was unrealistic across float64-native vs float32-exported computation.
- Q: What does "standards-compatible" mean for the export, given the character-level tokenizer? → A: The MODEL WEIGHTS and configuration load directly into a standards-compatible decoder-only inference tool without code changes. The character-level tokenizer is exported in the platform's own format and is NOT claimed to auto-load via a standard tokenizer auto-loader — tokenization may require the platform's adapter or manual character encoding.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Train a Llama-Compatible Model (Priority: P1)

A user trains a model on their own dataset using the anvil training interface. When training completes, the model is automatically serialized to safetensors as the primary artifact — complete with a standards-compatible configuration file and a tokenizer file. The safetensors checkpoint is stored, tracked, and versioned as the canonical output. Every tensor was learned during training — no synthetic or untrained parameters. The user can load the model weights and configuration directly into any tool that supports the target decoder-only transformer architecture, with no code changes to the model loading path. The native JSON format is also produced as a secondary internal representation.

**Why this priority**: This is the core value proposition — users can train locally and deploy anywhere. Without training functionality, nothing else works.

**Independent Test**: Can be fully tested by training a minimal model (1 layer, tiny embedding size) on a small corpus, observing the export produces a valid safetensors file, and verifying the exported model loads in an external compatible tool.

**Acceptance Scenarios**:

1. **Given** a user has configured training hyperparameters, **When** training completes successfully, **Then** a safetensors checkpoint (with config.json and tokenizer.json) is automatically produced as the primary artifact, and a native model.json is produced as a secondary representation.
2. **Given** a safetensors checkpoint is produced, **When** a user loads it via a Llama-compatible inference tool, **Then** the model loads without errors and produces sensible text output for seen training data.
3. **Given** a user trains a model with the new engine, **When** they inspect the state dict, **Then** it contains wte, lm_head, rms_final, layer{i}.attn_wq/wk/wv/wo, layer{i}.mlp_gate/up/down, and layer{i}.rms_1/rms_2 — no wpe, no fc1/fc2 keys, and no embedding-level norm parameter.
4. **Given** a user trains identical hyperparameters on the same data with the current and new engine, **When** training converges, **Then** the new engine achieves comparable loss (within expected variance from random initialization).

---

### User Story 2 - Learn the Llama Architecture Through Walkthroughs (Priority: P2)

A student progresses through the platform's six training walkthroughs (train0.py through train5.py). The progression teaches them: a single neuron, a linear layer, RMSNorm with learned weights, self-attention with RoPE, a transformer block with SwiGLU, and finally a full modern decoder-only transformer. By the end, the student has learned the architecture that powers today's most widely used LLMs.

**Why this priority**: The platform's educational value depends on walkthrough updates. Without them, students learn the old architecture, which doesn't match any modern model.

**Independent Test**: Can be tested by running each walkthrough script from train0.py to train5.py sequentially and verifying each produces the expected model components and loss behavior.

**Acceptance Scenarios**:

1. **Given** a student runs train2.py (RMSNorm), **When** training completes, **Then** the model has learned RMSNorm scale parameters (rms_1 per layer).
2. **Given** a student runs train3.py (self-attention), **When** inspecting attention computation, **Then** RoPE is applied to query and key vectors before the dot product.
3. **Given** a student runs train4.py (transformer block), **When** inspecting the MLP, **Then** it uses SiLU-gated SwiGLU (gate, up, down projections) rather than ReLU (fc1, fc2).
4. **Given** a student runs train5.py (full GPT), **When** they export the trained model, **Then** it produces a standards-compatible checkpoint with a valid architecture configuration.

---

### User Story 3 - Access and Share Trained Models (Priority: P3)

An engineer has trained a model on their custom corpus. The safetensors checkpoint was automatically generated, stored, and versioned during training. The engineer can access the checkpoint — model weights using standard tensor naming conventions, a configuration file, and a tokenizer file — through the platform's experiment tracking interface. They can download, re-export, or share this checkpoint for use in any standards-compatible inference tool.

**Why this priority**: This unlocks the "train once, run anywhere" value that justifies the architectural evolution, but is only meaningful after the engine itself works (Story 1).

**Independent Test**: Can be tested by exporting a trained model, loading it in a standards-compatible inference tool, running a forward pass, and comparing logits to the native anvil forward pass.

**Acceptance Scenarios**:

1. **Given** a trained model, **When** the export function runs, **Then** a model weights file is produced with standard tensor naming conventions for the target decoder-only architecture (model.embed_tokens.weight, model.layers.{i}.self_attn.q_proj.weight, etc.).
2. **Given** an exported model, **When** loaded in a standards-compatible inference tool configured with the correct activation function, **Then** the forward pass logits match the native anvil forward pass within floating-point tolerance.
3. **Given** an exported model directory, **When** a user inspects the configuration file, **Then** it includes the correct architecture type and all required configuration fields derived from training hyperparameters.

---

### Edge Cases

- What happens when a user tries to load an old-format model.json with the new engine? The state_dict keys don't match (wpe no longer exists, fc1/fc2 vs gate/up/down) — loading should fail with a clear error.
- How does the system handle very small embedding dimensions (e.g., n_embd=4)? RoPE computation with very few dimensions could produce numerical edge cases. Note: head_dim must be even (see FR-017) — configurations where head_dim would be odd are rejected at validation time.
- What happens when a user requests 0 transformer layers (n_layer=0)? The engine produces a valid model with no transformer blocks (embedding → final RMSNorm → lm_head).
- How does the demo model auto-retrain when the old demo model.json format is incompatible? The system should detect the format mismatch and retrain transparently.
- What happens if export dependencies (safetensors, numpy) are not installed? The export should fail with a clear, user-friendly installation instruction, and training itself remains successful (per FR-016).
- What happens if a user requests a configuration where head_dim is odd (e.g., n_embd=30, n_head=6 → head_dim=5)? Validation MUST reject it with a clear message, since RoPE requires an even head_dim (see FR-017).
- What happens if safetensors generation fails during training completion (disk full, permissions, etc.)? Training is still successful — the failure is flagged prominently in the UI/logs, and the user can retry generation later from the native JSON.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Core engine MUST replace the current ReLU-based MLP (fc1/fc2) with SwiGLU gated MLP (gate_proj, up_proj, down_proj) using intermediate size `int(8 * n_embd / 3)` to preserve parameter count parity.
- **FR-002**: Core engine MUST add learned RMSNorm scale parameters per transformer layer — `rms_1` (pre-attention) and `rms_2` (pre-MLP) — plus a single model-level `rms_final` scale applied before the output projection, all initialized to 1.0.
- **FR-003**: Core engine MUST replace learned position embeddings (wpe lookup table) with Rotary Position Encoding (RoPE) applied to query and key vectors at each attention head. RoPE MUST use the half-split (rotate_half) pairing convention — dimension `i` paired with dimension `i + head_dim/2` — matching the target decoder-only architecture, so exported weights load without permutation. The interleaved/consecutive pairing convention MUST NOT be used.
- **FR-004**: Training engine MUST support a SiLU (Swish) activation function with correct gradient computation during backpropagation.
- **FR-005**: Core engine MUST remove the wpe (position embedding) parameter from the state dict, as position information is now conveyed through RoPE.
- **FR-005a**: Core engine MUST remove the embedding-level normalization that exists in the current engine (applied immediately after token+position embedding). The target architecture has no embedding-level norm; normalization occurs only at pre-attention, pre-MLP, and final (pre-output) positions.
- **FR-006**: On every training completion, the system MUST automatically generate a safetensors checkpoint (model weights file + config + tokenizer) as the primary model artifact.
- **FR-007**: The safetensors checkpoint MUST use the standard tensor naming conventions for the modern decoder-only transformer architecture, covering ALL parameters: `model.embed_tokens.weight`; per layer `model.layers.{i}.self_attn.{q_proj,k_proj,v_proj,o_proj}.weight`, `model.layers.{i}.mlp.{gate_proj,up_proj,down_proj}.weight`, `model.layers.{i}.input_layernorm.weight`, `model.layers.{i}.post_attention_layernorm.weight`; `model.norm.weight`; and `lm_head.weight`. Tensor data MUST be written in the row-major `[out_features, in_features]` layout expected by the target architecture (transposing on export if the internal layout differs), and the SwiGLU branches MUST map correctly (`gate_proj` is the SiLU-activated branch, `up_proj` is the linear branch).
- **FR-008**: The safetensors checkpoint MUST be stored, tracked, and versioned alongside the training experiment. Each training run produces one immutable checkpoint version, keyed by experiment/run ID.
- **FR-009**: Export MUST be a zero-synthesis operation — every tensor in the safetensors file MUST correspond to a trained parameter (no synthetic biases or norm parameters).
- **FR-010**: The native model JSON format MUST update to reflect the new state dict keys and MUST NOT include wpe or fc1/fc2 keys. The JSON is a secondary/internal representation.
- **FR-011**: Loading an old-format model.json with the new engine MUST fail gracefully with a clear error message indicating the format is incompatible.
- **FR-012**: The demo model (`data/models/demo/model.json`) MUST auto-retrain on first load after the engine update.
- **FR-013**: Inference service MUST be updated to work with the new state dict structure (no wpe reference, new MLP key names).
- **FR-014**: Forward introspection widget MUST be updated to trace attention weights through the RoPE + SwiGLU flow.
- **FR-015**: Training walkthrough scripts (train0.py through train5.py) MUST be updated to teach the new architecture progression culminating in a full Llama-aligned model. The progression follows: train0 → single neuron, train1 → linear layer, train2 → RMSNorm with learned weights, train3 → self-attention with RoPE, train4 → transformer block with SwiGLU, train5 → full Llama-aligned GPT.
- **FR-016**: If safetensors generation fails during training completion, the training run MUST still be recorded as successful (loss is valid), the failure MUST be prominently flagged in the UI and logs, and the user MUST be able to retry generation later from the native JSON.
- **FR-017**: Model configuration validation MUST require that `head_dim = n_embd / n_head` is an even integer (equivalently, `n_embd` is divisible by `2 × n_head`). Configurations producing an odd head_dim MUST be rejected with a clear error, because RoPE pairs dimensions and requires an even head_dim.
- **FR-018**: When RoPE is applied with a per-position key/value cache, each key MUST be rotated at its own absolute position exactly once before being cached (queries are rotated at the current position; values are never rotated). The implementation MUST NOT double-rotate cached keys.
- **FR-019**: The GPU-accelerated training backend MUST produce a model whose architecture and state dict keys match the CPU engine (SwiGLU, RoPE, learned RMSNorm including rms_final, no wpe/fc1/fc2). Because the GPU backend's output is bridged into the canonical model representation for export and inference, the GPU and CPU engines MUST stay architecturally consistent — a GPU backend left on the old GPT-2 architecture would break the export and inference pipeline.

### Key Entities *(include if feature involves data)*

- **GPT State Dict**: The complete set of learned parameters for a model. Contains token embeddings (wte), per-layer attention projections (attn_wq/wk/wv/wo), per-layer SwiGLU MLP projections (mlp_gate/up/down), per-layer RMSNorm scales (rms_1/rms_2), a model-level final RMSNorm scale (rms_final), and output projection (lm_head). Contains NO wpe and NO embedding-level norm parameter.
- **Training Checkpoint (safetensors)**: The primary model artifact — a safetensors weights file with accompanying config.json and a tokenizer file. Uses standard tensor naming conventions for the target decoder-only architecture (all parameters covered per FR-007). Automatically generated, stored, tracked, and versioned on every training completion.
- **Internal Model State (JSON)**: A secondary representation of the model in native anvil JSON format. Contains hyperparameters (including intermediate_size) and the complete state dict. Used internally for in-platform operations (inference, introspection).
- **Tokenizer Vocabulary**: The sorted unique characters from the training corpus, stored as a character-level mapping. Generated during training and embedded in both checkpoint formats. The exported tokenizer file uses the platform's own character-level format; it is NOT a standard subword-tokenizer artifact and is not claimed to auto-load via a standard tokenizer auto-loader.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A trained model with n_embd=16, n_layer=1, n_head=4 completes training on a 1000-character corpus in under 60 seconds and produces a valid safetensors export.
- **SC-002**: Forward pass logits from the exported model (loaded by a standards-compatible tool) match a native anvil forward pass — computed in the SAME float precision as the export (float32) — within relative tolerance 1e-4 and absolute tolerance 1e-4 across 10 random input sequences. Token-level (argmax) agreement is verified separately and MUST be exact for the same sequences.
- **SC-003**: The exported model's configuration validates successfully against the target decoder-only transformer architecture schema for any combination of compatible model sizes (embedding dimension 16-768, depth 0-12, heads 2-12) where `head_dim = n_embd / n_head` is an even integer (per FR-017).
- **SC-004**: Users can train a model, export it, and load the MODEL WEIGHTS AND CONFIGURATION directly into a standards-compatible decoder-only inference tool without code changes to the model loading path. (Tokenization is out of scope for this claim — the character-level tokenizer uses the platform's own format and may require the platform's adapter or manual character encoding.)
- **SC-005**: All six walkthrough scripts (train0.py through train5.py) execute without errors and each produces a valid model with the correct architecture components for that lesson.

## Assumptions

- **Project identity**: This is the **anvil** project — the educational training and experimentation tier. anvil sits upstream of Foundry (model catalog, quantization, benchmarking) and Crucible (extensive eval & reporting). Models trained in anvil are designed for export into the broader ecosystem.
- The anvil training engine is being evolved — this is not a separate engine but an evolution of the existing one, replacing its components.
- The intermediate size for SwiGLU is `int(8 * n_embd / 3)` to maintain parameter count parity with the old ReLU MLP, following Llama convention.
- RoPE theta is set to 10000.0 (standard Llama default). RoPE uses the half-split (rotate_half) pairing convention (dimension `i` paired with `i + head_dim/2`), matching the target architecture — NOT interleaved/consecutive pairing.
- The demo model retrains automatically on first startup, so no manual migration of old demo checkpoints is needed.
- The safetensors checkpoint is the primary model artifact — generated, stored, tracked, and versioned automatically. The native JSON is a secondary representation for internal use only.
- The GPU-accelerated training backend MUST be evolved alongside the CPU engine to the same Llama architecture (per FR-019). Because the GPU backend's trained weights are bridged into the canonical model representation (keyed by state dict name) for export and inference, leaving the GPU path on the old GPT-2 architecture would break the pipeline. This corrects an earlier assumption that the GPU path could remain on the old architecture independently — that is not viable given the shared downstream representation.
- The character-level tokenizer approach is retained — no BPE or subword tokenization is introduced at this stage. The exported tokenizer file is in the platform's own format and is not a standard subword-tokenizer artifact.