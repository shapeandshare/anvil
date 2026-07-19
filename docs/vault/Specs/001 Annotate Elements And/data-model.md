# Data Model: Visual Feedback Annotation

## Entities

### FeedbackReport

Represents a single feedback submission — a collection of annotations captured at one point in time.

| Field | Type | Nullable | Default | Description |
|-------|------|----------|---------|-------------|
| `id` | `int` PK | No | auto | Primary key |
| `page_url` | `str` (512) | No | — | URL of the page where feedback was captured |
| `viewport_width` | `int` | No | — | Viewport width at capture time (px) |
| `viewport_height` | `int` | No | — | Viewport height at capture time (px) |
| `screenshot_path` | `str` (512) | Yes | `None` | Relative path in LocalFileStore to the raw screenshot |
| `annotated_path` | `str` (512) | Yes | `None` | Relative path in LocalFileStore to the annotated screenshot |
| `status` | `FeedbackStatus` | No | `OPEN` | Report status: `open`, `in_progress`, `resolved` |
| `reporter_id` | `str` (255) | No | `"default"` | String identifier of the submitting session (no FK — the codebase has no `User` table; follows the `UserSecret.user_id` string-identifier pattern; always `"default"` in single-user mode) |
| `notes_summary` | `str` (1000) | Yes | `None` | Optional brief summary of the issue |
| `created_at` | `datetime` | No | `utcnow()` | When the report was submitted |
| `updated_at` | `datetime` | No | `utcnow()` | Last update timestamp |

**Relationships**:
- `FeedbackReport` 1──N `FeedbackAnnotation` (cascade delete)

**Validation Rules**:
- `page_url` must be a valid URL path (starts with `/`)
- `viewport_width` and `viewport_height` must be positive integers
- `status` must be a valid `FeedbackStatus` enum value

---

### FeedbackAnnotation

Represents a single annotation (element marker, circle, or freehand stroke) within a feedback report.

| Field | Type | Nullable | Default | Description |
|-------|------|----------|---------|-------------|
| `id` | `int` PK | No | auto | Primary key |
| `report_id` | `int` FK | No | — | References parent `FeedbackReport` |
| `annotation_type` | `AnnotationType` | No | — | `element`, `circle`, or `freehand` |
| `note` | `str` (2000) | Yes | `None` | User's text description of the issue |
| `data` | `str` (JSON) | No | — | JSON blob with type-specific coordinate data |
| `order` | `int` | No | 0 | Display order within the report |
| `created_at` | `datetime` | No | `utcnow()` | When the annotation was added |

**Relationships**:
- `FeedbackAnnotation` N──1 `FeedbackReport` (via `report_id`)

**Validation Rules**:
- `annotation_type` must be a valid `AnnotationType` enum value
- `note` max 2000 characters
- `data` must be valid JSON matching the schema for the annotation type

#### Annotation Type Data Schemas

**Element** (`annotation_type: "element"`):
```json
{
  "x": 450,
  "y": 320,
  "width": 120,
  "height": 40,
  "selector": "button#train-submit",
  "tagName": "button",
  "innerText": "Submit"
}
```

**Circle** (`annotation_type: "circle"`):
```json
{
  "cx": 300,
  "cy": 200,
  "radius": 80
}
```

**Freehand** (`annotation_type: "freehand"`):
```json
{
  "path": [[100, 100], [120, 130], [150, 140]],
  "bounds": {"minX": 100, "minY": 100, "maxX": 150, "maxY": 140}
}
```

---

## Enums

Both enums live in `anvil/db/models/` (e.g., `feedback_status.py`, `annotation_type.py`), following the `teaching_session_status.py` precedent — DB-status enums co-locate with the ORM models that consume them, preserving layer discipline (the DB layer never imports from the service layer).

### FeedbackStatus (StrEnum)
```python
class FeedbackStatus(StrEnum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
```

### AnnotationType (StrEnum)
```python
class AnnotationType(StrEnum):
    ELEMENT = "element"
    CIRCLE = "circle"
    FREEHAND = "freehand"
```

---

## State Transitions

```
OPEN ──→ IN_PROGRESS ──→ RESOLVED
  ↑                          │
  └──────────────────────────┘
         (re-open)
```

- **OPEN**: Initial state when submitted
- **IN_PROGRESS**: Admin is reviewing/working on the report
- **RESOLVED**: Issue has been addressed
- Reports can be re-opened from RESOLVED back to OPEN

---

## File Storage

### LocalFileStore Paths

```
data/feedback/{report_id}/
├── screenshot.png       # Raw viewport screenshot (captured on annotation mode entry)
└── annotated.png        # Screenshot with annotations overlaid (generated on submit)
```

- `screenshot_path` and `annotated_path` in `FeedbackReport` store relative paths from the `feedback_dir` root
- Paths are stored as `{report_id}/screenshot.png` and `{report_id}/annotated.png`
- `LocalFileStore` is instantiated with `base_path = paths.feedback_dir`

### WorkspacePaths Addition

Add a `feedback_dir` property:
```python
@property
def feedback_dir(self) -> Path:
    """Directory for feedback report screenshots."""
    return self._base_dir / "data" / "feedback"
```

---

## Alembic Migration

A new hand-written numbered migration file `anvil/_resources/migrations/versions/015_add_feedback_reports.py` (following the `011_add_teaching_sessions.py` pattern) adds two tables:
- `feedback_reports` — columns matching `FeedbackReport` fields above
- `feedback_annotations` — columns matching `FeedbackAnnotation` fields above

Both tables use the existing `TimestampMixin` for `created_at`/`updated_at`. Migrations apply automatically at app startup via `ANVIL_DB_AUTO_MIGRATE` (there is no `make db-revision` target — migration files are written by hand with sequential numbering).