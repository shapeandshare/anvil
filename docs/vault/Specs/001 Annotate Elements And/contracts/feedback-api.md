# Feedback API Contract

## Endpoints

### Submit Feedback

```
POST /v1/feedback
Content-Type: multipart/form-data
```

**Request**:
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `page_url` | `str` | Yes | URL path of the page where feedback was captured |
| `viewport_width` | `int` | Yes | Viewport width at capture time |
| `viewport_height` | `int` | Yes | Viewport height at capture time |
| `screenshot` | file | Yes | PNG screenshot image (raw viewport) |
| `annotated` | file | Yes | PNG screenshot with annotations overlaid |
| `annotations` | `str` (JSON) | Yes | JSON string of annotation array |
| `notes_summary` | `str` | No | Optional brief summary |

**`annotations` JSON structure**:
```json
[
  {
    "type": "element",
    "note": "Button doesn't respond",
    "data": {
      "x": 450,
      "y": 320,
      "width": 120,
      "height": 40,
      "selector": "button#train-submit",
      "tagName": "button",
      "innerText": "Submit"
    }
  },
  {
    "type": "circle",
    "note": "Misaligned section",
    "data": {
      "cx": 300,
      "cy": 200,
      "radius": 80
    }
  }
]
```

**Response** `201 Created`:
```json
{
  "id": 123,
  "status": "open",
  "page_url": "/v1/training-page",
  "annotation_count": 2
}
```

**Errors**:
| Status | Condition |
|--------|-----------|
| 400 | Invalid/missing fields, malformed JSON, annotation type not recognized |
| 401 | Unauthenticated |
| 413 | Screenshot or annotations payload too large |

---

### List Feedback Reports

```
GET /v1/feedback?status=open&page=1&per_page=20
```

**Query Parameters**:
| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `status` | `str` | `all` | Filter by status: `open`, `in_progress`, `resolved`, `all` |
| `page` | `int` | 1 | Page number (1-indexed) |
| `per_page` | `int` | 20 | Items per page (max 100) |

**Response** `200 OK`:
```json
{
  "items": [
    {
      "id": 123,
      "page_url": "/v1/training-page",
      "status": "open",
      "notes_summary": null,
      "annotation_count": 2,
      "created_at": "2026-07-18T20:30:00Z",
      "updated_at": "2026-07-18T20:30:00Z"
    }
  ],
  "total": 42,
  "page": 1,
  "per_page": 20,
  "pages": 3
}
```

---

### Get Feedback Report

```
GET /v1/feedback/{id}
```

**Response** `200 OK`:
```json
{
  "id": 123,
  "page_url": "/v1/training-page",
  "viewport_width": 1440,
  "viewport_height": 900,
  "status": "open",
  "reporter_id": 1,
  "notes_summary": null,
  "annotations": [
    {
      "id": 1,
      "type": "element",
      "note": "Button doesn't respond",
      "data": {
        "x": 450,
        "y": 320,
        "width": 120,
        "height": 40,
        "selector": "button#train-submit"
      },
      "order": 0
    }
  ],
  "screenshot_url": "/v1/feedback/123/screenshot",
  "created_at": "2026-07-18T20:30:00Z",
  "updated_at": "2026-07-18T20:30:00Z"
}
```

**Errors**:
| Status | Condition |
|--------|-----------|
| 404 | Report not found |

---

### Serve Screenshot

```
GET /v1/feedback/{id}/screenshot
```

Returns the annotated screenshot image as `image/png`.

**Errors**:
| Status | Condition |
|--------|-----------|
| 404 | Report not found or no screenshot available |

---

### Export Report (JSON)

```
GET /v1/feedback/{id}/export
```

Returns the full report with annotations and all metadata as a JSON download (`application/json`). Does not include the screenshot base64 — screenshot is referenced by URL.

**Response** `200 OK` — same structure as GET `/v1/feedback/{id}` plus `screenshot_url` and `annotated_screenshot_url`.

**Errors**:
| Status | Condition |
|--------|-----------|
| 404 | Report not found |

---

### Update Report Status

```
PATCH /v1/feedback/{id}/status
Content-Type: application/json
```

**Request**:
```json
{
  "status": "in_progress"
}
```

**Response** `200 OK`:
```json
{
  "id": 123,
  "status": "in_progress",
  "updated_at": "2026-07-18T21:00:00Z"
}
```

**Errors**:
| Status | Condition |
|--------|-----------|
| 400 | Invalid status value |
| 404 | Report not found |

---

### Delete Report

```
DELETE /v1/feedback/{id}
```

Deletes the report, all associated annotations, and screenshot files from LocalFileStore.

**Response** `204 No Content`

**Errors**:
| Status | Condition |
|--------|-----------|
| 404 | Report not found |

---

### Batch Delete Reports

```
POST /v1/feedback/batch-delete
Content-Type: application/json
```

**Request**:
```json
{
  "ids": [1, 2, 3]
}
```

**Response** `200 OK`:
```json
{
  "deleted": 3
}
```

**Errors**:
| Status | Condition |
|--------|-----------|
| 400 | Empty or invalid IDs array |

---

## Web UI Page

```
GET /v1/feedback-page
```

Renders the feedback dashboard template. No JSON response — returns `text/html`.
