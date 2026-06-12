# Data Model: Model Registry Tracking

**Date**: 2026-06-11 | **Plan**: [plan.md](./plan.md) | **Spec**: [spec.md](../spec.md)

## Entities

### RegisteredModel

Represents a named model in the registry. Analogous to a named model in MLflow Model Registry.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `id` | Integer | PK, autoincrement | Unique identifier |
| `name` | String(255) | UNIQUE, NOT NULL | User-provided model name |
| `description` | String(1000) | NULLABLE | Optional user description |
| `created_at` | DateTime | NOT NULL, server_default=now() | Timestamp of first registration |
| `updated_at` | DateTime | NOT NULL, server_default=now(), onupdate=now() | Timestamp of last modification |

**Relationships**:
- `versions` → `ModelVersion` (one-to-many)
- `latest_version` → Computed: max(version) across related ModelVersion records

**Validation Rules**:
- Name must be unique (case-insensitive enforced at application level)
- Name must be non-empty, max 255 characters
- Description is optional, max 1000 characters

---

### ModelVersion

Represents a specific iteration of a registered model.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `id` | Integer | PK, autoincrement | Unique identifier |
| `model_id` | Integer | FK → registered_models.id, NOT NULL | Parent model |
| `version` | Integer | NOT NULL | Sequential version number (per model) |
| `experiment_id` | Integer | FK → experiments.id, NOT NULL | Source experiment |
| `dataset_name` | String(255) | NULLABLE | Name of dataset used for training |
| `artifact_path` | String(500) | NOT NULL | Path to model artifact in registry storage |
| `final_loss` | Float | NULLABLE | Training loss at completion |
| `hyperparameters_json` | Text | NULLABLE | JSON snapshot of training config |
| `created_at` | DateTime | NOT NULL, server_default=now() | Registration timestamp |
| `updated_at` | DateTime | NOT NULL, server_default=now(), onupdate=now() | Last modification timestamp |

**Constraints**:
- UNIQUE(model_id, version) — no duplicate version numbers per model
- FK(model_id) → registered_models.id ON DELETE CASCADE — deleting a model removes all versions
- FK(experiment_id) → experiments.id — source experiment tracked for lineage

**Validation Rules**:
- Version auto-incremented per model (computed: max existing version + 1)
- Experiment must have status == "completed" at registration time
- Artifact path must be non-empty

---

## Entity Relationship Diagram

```
registered_models (1) ──── (N) model_versions
                                    │
                                    │ FK
                                    ▼
                              experiments
```

## State Transitions

### RegisteredModel Lifecycle

```
[Created upon first registration]
  │
  ▼
Active ──→ [User deletes model]
              │
              ▼
            Deleted (cascades to all versions)
```

### ModelVersion Lifecycle

```
[Created upon registration of a trained experiment]
  │
  ▼
Active ──→ [User deletes version]
              │
              ▼
            Deleted (artifact removed from storage)
```

## Data Volume Estimates

| Entity | Est. Growth | Notes |
|--------|-------------|-------|
| RegisteredModel | 10-100 models | Single-user local tool |
| ModelVersion | 1-20 versions per model | Users may iterate |
| Artifact files | ~100KB-1MB each | JSON model files