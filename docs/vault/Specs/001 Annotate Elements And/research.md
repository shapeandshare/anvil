# Research: Visual Feedback Annotation

**Phase 0 output** — Technology decisions and research consolidations for the Visual Feedback Annotation feature.

## 1. Screenshot Capture Library

### Decision
Use **`html-to-image`** (CDN-loaded) for client-side DOM → canvas screenshot capture.

### Rationale
- 4.5M weekly npm downloads — the most widely used and battle-tested library in this category
- Uses `foreignObject` approach (clone DOM → embed in SVG → let browser render) rather than HTML2Canvas's JS CSS re-painter
- Significantly faster and more accurate than html2canvas — especially for web fonts, CSS variables, and modern layout
- APIs are trivial: `import { toPng } from 'html-to-image'` → `toPng(element).then(dataUrl => ...)`
- No canvas tainting from cross-origin resources (browser handles rendering natively)
- Actively maintained (unlike html2canvas which has had zero commits since Jan 2022)

### Alternatives Considered
| Alternative | Rejected Because |
|-------------|-----------------|
| **html2canvas** | Unmaintained since 2022 (1,050+ open issues). Slow on anything beyond trivial DOMs. Cannot capture Shadow DOM or modern CSS reliably. Readme itself says "experimental — not recommended for production." |
| **SnapDOM** | Newer, good fidelity, but smaller ecosystem. Less battle-tested. |
| **modern-screenshot** | TypeScript-first — harder to integrate via CDN in vanilla JS project. |
| **Server-side headless browser** | Adds infrastructure complexity (chromium/playwright on server). Violates Simplicity First §11.1. |

### Integration Approach
- Load `html-to-image` from CDN (`https://cdn.jsdelivr.net/npm/html-to-image@1.11.11/+esm`) as an ES module
- Alternatively vendor it into `anvil/api/static/js/lib/html-to-image.js` for offline/air-gapped use
- Call `toPng(document.body, { pixelRatio: devicePixelRatio })` when annotation mode activates
- The resulting data URL becomes the background of the annotation canvas

---

## 2. Annotation Canvas Implementation

### Decision
Vanilla HTML5 Canvas API with a dedicated `AnnotationCanvas` class, following the existing `LossChart` pattern from `anvil/api/static/js/chart.js`.

### Rationale
- The project has zero frontend dependencies and no bundler — adding one would violate Constitution §11.2 and §11.4
- Existing canvas patterns (LossChart, GraphView, particle-system) prove the approach works well in this codebase
- The required drawing operations are simple: line strokes, circles, and freehand paths — all well within Canvas API capabilities
- No need for a heavyweight drawing library (Fabric.js, Konva, Paper.js) for this use case

### Pattern Reference
Following the `LossChart` pattern from `chart.js`:
```javascript
(function() {
  'use strict';

  function AnnotationCanvas(container) {
    this.container = container;
    this.canvas = null;
    this.ctx = null;
    this.annotations = [];
    this._currentTool = 'element'; // 'element' | 'circle' | 'freehand'
  }

  AnnotationCanvas.prototype._initCanvas = function(dataUrl) {
    var rect = this.container.getBoundingClientRect();
    var dpr = window.devicePixelRatio || 1;
    this.canvas = document.createElement('canvas');
    this.canvas.width = rect.width * dpr;
    this.canvas.height = rect.height * dpr;
    this.canvas.style.width = rect.width + 'px';
    this.canvas.style.height = rect.height + 'px';
    this.ctx = this.canvas.getContext('2d');
    this.ctx.scale(dpr, dpr);
  };

  window.AnnotationCanvas = AnnotationCanvas;
})();
```

---

## 3. Feedback Dashboard Integration

### Decision
Create a **new standalone admin page** at `/v1/feedback-page` rather than embedding in the existing operations page.

### Rationale
- The feedback dashboard has its own distinct lifecycle (list → view → export → status update → delete)
- Embedding would crowd the already-dense operations page (which has 6 sections: resources, services, actions, backups, logs, notifications)
- A dedicated nav tab makes the feature discoverable
- Follows same pattern as every other page in the app (each gets its own route and template)

### Template Pattern
Following the standard page pattern from `base.html` and `operations.html`:
- `feedback.html` extends `base.html`
- Uses `div.section-card` with staggered entrance animations (`style="--stagger-i: N"`)
- Report list uses `.grouped-list` table with `dom.syncTableBody` for reactive updates
- Review modal uses `.modal-overlay` + `.modal-dialog` (existing components.css pattern)

---

## 4. Feedback Data Model

### Decision
Two new DB models: `FeedbackReport` (report metadata) and `FeedbackAnnotation` (individual annotations within a report).

### Rationale
- Follows existing DB model patterns (one class per file, SQLAlchemy mapped_column, TimestampMixin)
- Separating report metadata from annotations avoids JSON blobs in a single column
- Enables future features (filtering by annotation type, searching notes) without migration
- `storage_path` on `FeedbackReport` references the screenshot in LocalFileStore — same pattern as `ModelAsset`, `FineTuneDataset`, `LoRAAdapter`

### Storage Path Pattern
```
data/feedback/{report_id}/screenshot.png        # Viewport screenshot
data/feedback/{report_id}/annotated.png         # Screenshot with annotations overlaid
```

---

## 5. FileStore Pattern

### Decision
Reuse existing `LocalFileStore` — no store subclass needed.

### Rationale
- `LocalFileStore` already handles arbitrary path prefixes — it's a generic key-value store
- Path `feedback/{report_id}/screenshot.png` is clean and isolated from other domains
- Add `feedback_dir` property to `WorkspacePaths` for future extensibility
- Same pattern as every other file-backed entity in the codebase

---

## 6. JavaScript Architecture

### Decision
Single new file `anvil/api/static/js/annotation.js` using the established IIFE + prototype pattern. Loaded via `{% block scripts %}` on pages that need it, plus globally on `base.html` for the floating annotation toggle button.

### Rationale
- Follows exact same pattern as every other JS file in the project (IIFE, no modules, no bundler)
- Annotation functionality is self-contained — it only needs the canvas element and DOM access
- Exposed as `window.AnnotationCanvas` following `window.LossChart`, `window.GraphView` convention
- Colors use CSS custom properties: `getComputedStyle(doc.documentElement).getPropertyValue('--accent')`

---

## 7. CSS Approach

### Decision
New file `anvil/api/static/css/feedback.css` for annotation-specific styles. Annotation overlay positioning and canvas sizing use existing design tokens.

### Rationale
- Annotation mode has unique overlay requirements (full-viewport canvas, floating toolbar, annotation markers)
- Minor additions don't warrant modifying `components.css` or `archetypes.css`
- Follows existing CSS file separation (tokens.css, components.css, archetypes.css, utilities.css, code.css)

---

## 8. Report Export Format

### Decision
JSON export following this structure:
```json
{
  "report_id": 123,
  "page_url": "/v1/training-page",
  "timestamp": "2026-07-18T20:30:00Z",
  "reporter": "user@example.com",
  "status": "open",
  "screenshot_url": "/v1/feedback/123/screenshot",
  "annotations": [
    {
      "type": "element",
      "selector": "button#train-submit",
      "x": 450,
      "y": 320,
      "width": 120,
      "height": 40,
      "note": "This button doesn't respond when clicked"
    },
    {
      "type": "circle",
      "cx": 300,
      "cy": 200,
      "radius": 80,
      "note": "This section is misaligned"
    },
    {
      "type": "freehand",
      "path": [[100, 100], [120, 130], [150, 140], ...],
      "note": "Visual glitch in this area"
    }
  ]
}
```

### Rationale
- Machine-readable for automated agent consumption (user explicitly requested this)
- Annotation coordinates are relative to the captured viewport (position-independent of page layout)
- Element selectors provide DOM-level targeting for developers who want to inspect the actual element
- Base64 screenshot is excluded from JSON export and served separately as an image URL to keep exports manageable

---

## 9. Backend API Routes

| Method | Route | Purpose |
|--------|-------|---------|
| `POST` | `/v1/feedback` | Submit a new feedback report |
| `GET` | `/v1/feedback` | List feedback reports (paginated, filterable by status) |
| `GET` | `/v1/feedback/{id}` | Get a single report with all annotations |
| `GET` | `/v1/feedback/{id}/screenshot` | Serve the annotated screenshot image |
| `GET` | `/v1/feedback/{id}/export` | Export report as JSON (for agent consumption) |
| `PATCH` | `/v1/feedback/{id}/status` | Update report status |
| `DELETE` | `/v1/feedback/{id}` | Delete a single report |
| `POST` | `/v1/feedback/batch-delete` | Delete multiple reports |
| `GET` | `/v1/feedback-page` | Render the feedback dashboard page |

### Route Handler Pattern
Following existing pattern in `anvil/api/v1/pages.py`:
```python
@router.get("/feedback-page", response_class=HTMLResponse)
async def feedback_page(request: Request) -> HTMLResponse:
    return request.app.state.templates.TemplateResponse(
        request,
        "feedback.html",
        {},
    )
```
