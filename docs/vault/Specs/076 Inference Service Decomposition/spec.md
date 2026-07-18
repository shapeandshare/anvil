# Feature Specification: Split InferenceService into Domain-Focused Services

**Feature Branch**: `opencode/witty-forest`  
**Created**: 2026-07-18  
**Status**: Draft  
**Priority**: P2  
**Input**: Codebase review finding #076 — `InferenceService` (`anvil/services/inference/inference.py`) is 1400+ lines with responsibilities spanning model loading, tokenization, embeddings extraction, attention visualization, sampling distributions, computation graphs, loss breakdowns, and demo model warmup. Violates the Single Responsibility Principle.

## User Scenarios & Testing

### User Story 1 - Focused service classes (Priority: P2)

Each inference-related concern lives in its own service class with a clear responsibility boundary. `InferenceService` becomes an orchestrator that delegates to focused sub-services.

**Why this priority**: 1400+ line classes are hard to understand, test, and modify. A single change to tokenization requires navigating past sampling and attention logic. Separation makes each unit independently testable and maintainable.

**Independent Test**: The tokenization service can be unit-tested without loading a model; the model-loading service can be tested without tokenization.

**Acceptance Scenarios**:

1. **Given** a new model needs to be loaded, **When** `ModelLoadingService.load(model_id, version)` is called, **Then** it returns a `LoadedModel` without performing any tokenization or sampling.
2. **Given** input text needs tokenization, **When** `TokenizationService.tokenize(text, loaded_model)` is called, **Then** it returns token IDs without loading any model.
3. **Given** a loaded model needs sampling, **When** `SamplingService.generate(loaded_model, prompt, temperature, top_k, top_p)` is called, **Then** it produces text without loading models or tokenizing inputs.

---

### User Story 2 - Backward-compatible public API (Priority: P2)

Existing callers of `InferenceService` continue to work without knowing about the internal decomposition.

**Why this priority**: `InferenceService` is used by routes (`inference.py`), `TrainingRunService`, `EvaluationService`, `TeachingService`, and `_pyfunc_model.py`. A breaking change would require updating all callers simultaneously.

**Independent Test**: All existing tests for `InferenceService` continue to pass without modification.

**Acceptance Scenarios**:

1. **Given** `InferenceService.load_model(model_id, version)` is called, **When** the internal implementation changes, **Then** the public API and return type are unchanged.
2. **Given** `InferenceService.generate(body)` is called, **When** internally it delegates to `SamplingService`, **Then** the response is identical to before.

### Edge Cases

- The demo model warmup runs in a background thread — this should be delegated to a dedicated `DemoModelWarmupService`.
- The `_call_or_400` wrapper in `inference.py` routes needs to adapt to the new service structure.
- Tokenizer factory and model mapping logic (`_hf_to_anvil_key`, `_STATIC_HF_MAP`) should live with the model loading service.

## Requirements

### Functional Requirements

- **FR-001**: `InferenceService` MUST be decomposed into focused sub-services, each with a single responsibility.
- **FR-002**: Suggested decomposition (implementer may adjust):
  - **ModelLoadingService**: Load models (from catalog, from ref, from MLflow), mapping HF keys, warmup.
  - **TokenizationService**: Tokenize, get embeddings, get attention patterns.
  - **SamplingService**: Generate text, sample distributions, top-k/top-p filtering.
  - **LossService**: Compute loss, get logits, get probabilities.
- **FR-003**: `InferenceService` MUST remain as a facade that delegates to the sub-services, preserving its public API.
- **FR-004**: Sub-services MUST be injectable via constructor (so `InferenceService` receives them, not creates them).
- **FR-005**: All existing tests MUST pass without modification to test assertions.
- **FR-006**: Each new sub-service MUST have its own unit test file.

### Key Entities

- **InferenceService**: Facade (existing, continues to work)
- **ModelLoadingService**: Sub-service for model loading (new)
- **TokenizationService**: Sub-service for tokenization/embeddings (new)
- **SamplingService**: Sub-service for generation (new)
- **LossService**: Sub-service for loss/logits (new)

## Success Criteria

### Measurable Outcomes

- **SC-001**: `InferenceService` reduced from 1400+ lines to <300 lines (facade).
- **SC-002**: Each sub-service is <400 lines.
- **SC-003**: Each sub-service has its own dedicated test file.
- **SC-004**: All existing tests pass without modification.
- **SC-005**: `make test` and `make typecheck` pass.

## Assumptions

- The decomposition boundaries may be adjusted by the implementer based on actual coupling between concerns.
- The facade pattern preserves backward compatibility (no caller changes needed).
- Shared state (e.g., cached loaded model) is managed in the facade or a shared context object.
