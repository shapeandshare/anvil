---
title: 003 Model Registry Tracking - research
type: research
tags:
  - type/spec
spec-refs:
  - docs/vault/Specs/003 Model Registry Tracking/
related:
  - '[[003 Model Registry Tracking]]'
created: ~
updated: ~
---
# Research: Model Registry Tracking

**Date**: 2026-06-11 | **Plan**: [plan.md](./plan.md)

## Technical Decisions

### Decision 1: Registry Artifact Storage

- **Decision**: Copy model artifacts to independent registry storage (FileStore) at registration time
- **Rationale**: Provides complete independence from experiment/MLflow storage. Deleting experiments does not break registered models. Matches MLflow Model Registry pattern of "copy-on-register."
- **Alternatives considered**:
  - Reference experiment artifacts (lighter but fragile — experiment deletion breaks registry)
  - Hybrid copy-on-first-access (complex, no clear benefit for v1)

### Decision 2: Version Numbering

- **Decision**: Simple sequential integers (1, 2, 3...) per model name
- **Rationale**: Intuitive, matches MLflow Model Registry convention, easy to display and compare. A model's first registration is v1, second is v2, etc.
- **Alternatives considered**:
  - Timestamp-based (less human-readable for comparison)
  - Semver (over-engineered for a local tool)

### Decision 3: Model Organization

- **Decision**: Chronological list sorted by most recently registered, with name search/filter
- **Rationale**: Covers the basic use case well. Search by name prevents the registry from becoming unusable as it grows. Tags, filtering, and advanced search can wait.
- **Alternatives considered**:
  - Simple chronological list only (becomes unusable with many models)
  - Tag-based organization (over-engineered for v1)
  - Full advanced search (future enhancement)

### Decision 4: Model/Version Deletion

- **Decision**: Users can delete individual versions or entire models with confirmation dialogs
- **Rationale**: Users will want to clean up. Deletion is the natural counterpart to creation. Confirmation prevents accidents. Warning if in-use prevents broken inference sessions.
- **Alternatives considered**:
  - No deletion (append-only — clutters registry, frustrating UX)
  - Soft-delete only (adds complexity without clear benefit for v1)

### Decision 5: Training Metadata in Model Versions

- **Decision**: Capture experiment source, training loss, hyperparameters, trained-on dataset name, and registration timestamp
- **Rationale**: Full provenance for reproducibility. Dataset name is low-cost (already linked to experiment) and high-value for users training on multiple datasets.
- **Alternatives considered**:
  - Minimal metadata (experiment ID only — requires click-through for every detail)
  - Full training trace (loss curve, all checkpoints — over-engineered for v1)

## Architecture Approach

### Component Chain

```
Migration (new tables)
  → ORM Models (RegisteredModel, ModelVersion)
    → Repository (RegistryRepository)
      → Service (ModelRegistryService)
        → API Routes (/v1/registry/)
          → Jinja2 Templates (registry.html, model_detail.html)
```

### Integration Points

| Component | File | Change |
|-----------|------|--------|
| Training callback | `anvil/api/v1/training.py` | Expose model artifact path in experiment detail for "Register Model" action |
| Experiment list UI | `templates/experiments.html` | Add "Register Model" button for completed experiments |
| Inference endpoints | `router.py` | Change `/v1/inference/models` to query registry instead of experiments |
| God class | `cli.py` | Expose `ModelRegistryService` via property |
| Migration chain | `migrations/versions/` | Create `002_add_model_registry.py` pointing to `001` |

### Storage Strategy Detail

Registry artifacts stored using the existing `LocalFileStore` at `data/models/registry/`:
- Path pattern: `data/models/registry/{model_name}/v{version_number}/model.json`
- On registration: copy artifact from temp dir (where training saves it) to registry path
- On version deletion: remove the specific version directory
- On model deletion: remove the entire model directory tree

### UI Pattern

Follow existing retro terminal theme:
- Registry list page: htop-style rows (matching experiments.html pattern)
- Model detail page: version history table with clickable rows
- "Register Model" button: appears as a terminal-style button on experiment rows
- Inference page: replace experiment dropdown with registry model/version dropdown