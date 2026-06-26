---
title: 'Data Model: Non-Educational Help Guide'
type: spec
tags:
  - type/spec
  - domain/vault
status: draft
created: '2026-06-22'
updated: '2026-06-22'
---

Back to [[Specs/001 Non-Educational Help Guide/spec]].

# Data Model: Non-Educational Help Guide

**Phase**: 1 | **Date**: 2026-06-22
**Feature**: Non-Educational Help Guide

## Entity: HelpSection

A single help section covering one non-educational workspace page.

### Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `anchor_id` | `str` | Yes | URL anchor ID for deep-linking (e.g. `"training"`, `"data"`) |
| `title` | `str` | Yes | Display heading (e.g. `"Training Dashboard"`) |
| `route` | `str` | Yes | Path to the workspace page (e.g. `"/v1/training-page"`) |
| `description` | `str` | Yes | One-sentence summary for the index listing |
| `content` | `str` | Yes | Full help body — HTML rendered by the template (supports inline tags for emphasis, links, code) |
| `related_lesson_keys` | `list[str]` | No | Keys into `LEARNING_ARC` for "Related lessons" links (default `[]`) |

### Validation Rules

- `anchor_id` MUST be unique across all sections
- `anchor_id` MUST match `^[a-z0-9-]+$` (lowercase kebab-case)
- `title` MUST be non-empty
- `route` MUST be a valid absolute or relative URL path (starts with `/`)
- `content` SHALL NOT contain unsupported HTML tags per the design system

### Implementation (Pydantic BaseModel)

```python
from pydantic import BaseModel


class HelpSection(BaseModel):
    """Help content for one non-educational workspace page."""

    anchor_id: str
    title: str
    route: str
    description: str
    content: str
    related_lesson_keys: list[str] = []
```

### Example Instance

```python
HelpSection(
    anchor_id="training",
    title="Training Dashboard",
    route="/v1/training-page",
    description=(
        "Configure hyperparameters, start training runs, "
        "and monitor loss curves in real time."
    ),
    content=(
        "<p>The Training Dashboard is the main workspace for "
        "training language models. Use it to configure runs, "
        "start training, and watch results stream in real time.</p>"
        "<h3>Key Controls</h3>"
        "<ul>"
        "<li><strong>Model Config</strong> — Set n_embd, n_layer, n_head, "
        "learning_rate, num_steps, and temperature.</li>"
        "<li><strong>Data Source</strong> — Pick a dataset or corpus to "
        "train on.</li>"
        "<li><strong>Compute Backend</strong> — Choose CPU, GPU, or "
        "cloud (Modal).</li>"
        "</ul>"
    ),
    related_lesson_keys=["parameters", "training-loop", "architecture"],
)
```

### State Transitions

None. `HelpSection` instances are static — they are authored in code and rendered
at page-request time. Content changes are made by editing the data module directly.

## Collection: `HELP_SECTIONS`

Ordered list of `HelpSection` instances that defines the rendering order on the
help page.

```python
HELP_SECTIONS: list[HelpSection] = [
    ...
]
```

Index order determines display order (top to bottom on the single-page layout).

## Relationships

- `related_lesson_keys` references entries in `LEARNING_ARC` (defined in
  `anvil/api/v1/learning.py`) — a weak, string-keyed foreign key relationship.
  Unknown keys are silently ignored (at render time).