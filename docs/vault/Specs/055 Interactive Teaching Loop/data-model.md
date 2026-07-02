# Data Model: Interactive Teaching Loop (055)

> **Architecture correction (2026-07-02)**: Deep codebase verification (see research.md §9-§12) revealed that the model-reference identifier used by warm-start and inference is the **native integer experiment id** that persists the loadable artifact at `data/models/experiment_{id}.json` — NOT `ExternalModel.id`. `ExternalModel.id` is only created via the HuggingFace/local import workflow and is used by `EvaluationService`. These are different ID spaces. This data model uses the native experiment id (the identifier the training/inference layers already agree on) and does NOT introduce an `ExternalModel` FK.

## Entities

### TeachingSession — lightweight DB table (new)

The session row is the **chain head** — it holds the current base experiment id that the next round warm-starts from. Round lineage lives in MLflow tags, but the session row is the authoritative pointer to "where the chain currently is" (do not rely on MLflow tag scraping to find the next base).

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `id` | `int` | PK, auto-increment | Session identifier |
| `name` | `str` | NOT NULL, max 255 chars | User-facing session name |
| `description` | `str` | NULLABLE | Optional session description |
| `seed_experiment_id` | `int` | NULLABLE | The experiment id the session started from (null = trained from scratch in round 1). Provenance only. |
| `current_base_experiment_id` | `int` | NULLABLE | The experiment id the NEXT round warm-starts from. Null before round 1. Updated to the newly-persisted model id ONLY after a round's training finalization succeeds. |
| `status` | `TeachingSessionStatus` | NOT NULL, default `DRAFT` | `DRAFT` → `ACTIVE` → `COMPLETED` |
| `created_at` | `datetime` | NOT NULL, auto-set | When session was created |
| `updated_at` | `datetime` | NOT NULL, auto-updated | Last modification timestamp |

```sql
CREATE TABLE teaching_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    seed_experiment_id INTEGER,
    current_base_experiment_id INTEGER,
    status VARCHAR(16) NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft', 'active', 'completed')),
    created_at TIMESTAMP NOT NULL DEFAULT (datetime('now')),
    updated_at TIMESTAMP NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX idx_teaching_sessions_status ON teaching_sessions(status);
CREATE INDEX idx_teaching_sessions_created ON teaching_sessions(created_at);
```

> **No FK to external_models.** `current_base_experiment_id` / `seed_experiment_id` are native experiment ids (the same identifier space used by `TrainConfig.base_model_ref` and `InferenceService.load_model(model_id)`). There is intentionally no FK constraint because experiment artifacts are filesystem/MLflow entities, not a DB table.

### TeachingSessionStatus — StrEnum (new)

Per constitution Principle 11 (enums over magic strings):

```python
from enum import StrEnum

class TeachingSessionStatus(StrEnum):
    DRAFT = "draft"          # base selected/none, no rounds yet
    ACTIVE = "active"        # at least one round in progress or complete
    COMPLETED = "completed"  # learner marked done; read-only
```

### TeachingRound — tagged MLflow run (NOT a DB table)

TeachingRound is not a new entity — it IS the training run created for that round. It reuses the existing training pipeline via the new `TrainingRunService` coordinator (see plan.md). All artifacts (persisted model at `data/models/experiment_{id}.json`, dataset, MLflow run) are native entities, independently visible outside teaching.

**MLflow Tags (set during round finalization):**

| Tag | Value Type | Required | Description |
|-----|-----------|----------|-------------|
| `anvil.origin` | `"teaching"` | Yes | Distinguishes from one-shot training runs |
| `teaching_session_id` | `int` | Yes | Reference to TeachingSession.id |
| `teaching_round_index` | `int` | Yes | 1-based round number within session |
| `teaching_parent_experiment_id` | `int` | No (null for round 1 from scratch) | The experiment id this round warm-started from |
| `anvil.warm_start` | `"true"` | When chained | Reuses existing warm-start tag |
| `anvil.base_model_ref` | `int` | When chained | Reuses existing warm-start tag (= parent experiment id) |

> MLflow tags provide lineage/history for display. They are NOT the source of truth for "next base" — the session row's `current_base_experiment_id` is.

**Persisted artifacts (produced by existing training finalization):**

| Artifact | Path | Notes |
|----------|------|-------|
| Loadable model | `data/models/experiment_{experiment_id}.json` | THE artifact that makes the round's model loadable by `InferenceService.load_model(experiment_id)` |
| Safetensors export | MLflow run artifacts | Existing behavior |
| Round dataset | via `DatasetImportService.commit_docs_import()` | `origin` set to `teaching` (see §Dataset) |

## Lifecycle States

### TeachingSession

```
┌─────────┐  first round      ┌────────┐   learner     ┌───────────┐
│  DRAFT  │ ─── finalizes ──→ │ ACTIVE │ ── marks ───→ │ COMPLETED │
│         │  (sets current    │        │    done       │ (read-only)│
└─────────┘   base exp. id)   └────────┘               └───────────┘
                                    ↕
                          add rounds (each success updates
                          current_base_experiment_id)
```

- **DRAFT**: Session created. `current_base_experiment_id` may be set (seed) or null (from scratch). No completed rounds.
- **ACTIVE**: At least one round finalized. `current_base_experiment_id` points to the latest model. Learner can add rounds, inspect.
- **COMPLETED**: Learner marks done. Read-only. No more rounds.

## State Transition Rules

| Transition | Trigger | Validation |
|------------|---------|------------|
| DRAFT → ACTIVE | First round training finalizes successfully | Session exists |
| ACTIVE → ACTIVE | Subsequent round finalizes | `current_base_experiment_id` updated to new model id ONLY after finalization |
| ACTIVE → COMPLETED | Learner clicks "Mark Complete" | No round currently training |
| Rollback (ACTIVE) | Learner selects a prior round and branches | New round warm-starts from the selected round's experiment id; a new round is appended (parent tag points to selected round). Old rounds remain visible. `current_base_experiment_id` updates to the new round's model on finalization. |

## Validation Rules

1. `current_base_experiment_id`, when set, must correspond to an existing loadable artifact (`data/models/experiment_{id}.json`) — validated via `InferenceService.load_model()` before starting a round.
2. `teaching_round_index` values within a session are strictly sequential (1, 2, 3...) — enforced by the service layer.
3. Round 1 either warm-starts from `seed_experiment_id` or trains from scratch (no parent).
4. `current_base_experiment_id` is updated ONLY after a round's training finalization succeeds (never optimistically).
5. Sessions in `COMPLETED` status reject all mutation operations except read and delete.

## Dataset origin (teaching-created datasets)

Each round's examples become a dataset via `DatasetImportService.commit_docs_import(docs)`. The `Dataset.origin` field (existing, freeform `String(20)`, default `"user"`) SHALL be set to `"teaching"` so teaching-created datasets are queryable without MLflow-only discovery. This is a minor boundary change — the import service / repository must accept and persist an `origin` value.

> Per constitution Principle 11, if a fixed origin vocabulary is introduced, use a `StrEnum` (`DatasetOrigin`). If the field stays freeform for now, at minimum set the value `"teaching"` at the teaching boundary.

## Constraints & Indexes

- `teaching_sessions.status` indexed for listing/filtering.
- `teaching_sessions.created_at` indexed for chronological listing.
- Session delete does NOT cascade to MLflow runs or experiment artifacts (they remain independently accessible).

## Initial Migration

```python
"""Add teaching_sessions table.

Revision ID: 055_add_teaching_sessions
Revises: <parent_revision>
"""
from alembic import op
import sqlalchemy as sa

revision = "055_add_teaching_sessions"
down_revision = "<parent_revision>"  # determined at migration time via make db-revision

def upgrade() -> None:
    op.create_table(
        "teaching_sessions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("seed_experiment_id", sa.Integer(), nullable=True),
        sa.Column("current_base_experiment_id", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="draft"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("idx_teaching_sessions_status", "teaching_sessions", ["status"])
    op.create_index("idx_teaching_sessions_created", "teaching_sessions", ["created_at"])

def downgrade() -> None:
    op.drop_index("idx_teaching_sessions_created", table_name="teaching_sessions")
    op.drop_index("idx_teaching_sessions_status", table_name="teaching_sessions")
    op.drop_table("teaching_sessions")
```
