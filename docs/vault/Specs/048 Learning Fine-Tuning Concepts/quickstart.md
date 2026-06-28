---
title: Quickstart — Learning Fine-Tuning Concepts
type: spec
tags:
  - type/spec
created: '2026-06-28'
updated: '2026-06-28'
---
# Quickstart: Learning Fine-Tuning Concepts

## Implementation Steps

All changes are within existing files. No new Python modules, database migrations, or configuration.

### Step 1: Add Step Data Arrays

File: `anvil/api/v1/learning.py`

Add three new step arrays after the existing `EXPORT_STEPS` block (after line ~1122):

1. `FINE_TUNING_INTRO_STEPS` — 5 steps, no widget
2. `WARMSTART_VS_LORA_STEPS` — 6 steps, widget: `"lora"` on 2-3 steps
3. `FINETUNE_VS_PROMPT_VS_RAG_STEPS` — 5 steps, comparison table in body

**Step content guidelines**:
- Use the existing body style (HTML with `<b>`, `<code>`, `<a>`, `&mdash;`)
- Warm-start vs PEFT/LoRA page: include slider-based rank visualization widget
- Fine-tune vs prompt vs RAG page: embed comparison table in one step's body
- "Coming soon" forward links: use `<span class="coming-soon-badge">` for unshipped 039/044 capabilities

### Step 2: Add LEARNING_ARC Entries

File: `anvil/api/v1/learning.py` — insert after line 173 (after `"export"` entry)

```python
{
    "key": "fine-tuning-intro",
    "title": "What Fine-Tuning Is",
    "path": "/v1/learn/fine-tuning-intro",
    "desc": "What fine-tuning means in the context of LLMs — continued training of a pre-trained model on new data.",
},
{
    "key": "warmstart-vs-lora",
    "title": "Warm-Start vs PEFT/LoRA",
    "path": "/v1/learn/warmstart-vs-lora",
    "desc": "How full fine-tuning (warm-start) differs from parameter-efficient approaches like LoRA, and the low-rank intuition behind adapters.",
},
{
    "key": "finetune-vs-prompt-vs-rag",
    "title": "Fine-Tune vs Prompt vs RAG",
    "path": "/v1/learn/finetune-vs-prompt-vs-rag",
    "desc": "When to fine-tune, when to prompt-engineer, and when to use retrieval-augmented generation — a decision comparison.",
},
```

### Step 3: Add Route Handlers

File: `anvil/api/v1/learning.py` — add after `export_concept_page` (after line ~2105)

```python
@router.get("/learn/fine-tuning-intro", response_class=HTMLResponse)
async def fine_tuning_intro_page(request: Request) -> HTMLResponse:
    """Render the fine-tuning introduction walkthrough page."""
    return request.app.state.templates.TemplateResponse(  # type: ignore[no-any-return]
        request,
        "archetypes/concept.html",
        {"steps": FINE_TUNING_INTRO_STEPS, **_arc_context("fine-tuning-intro")},
    )

@router.get("/learn/warmstart-vs-lora", response_class=HTMLResponse)
async def warmstart_vs_lora_page(request: Request) -> HTMLResponse:
    """Render the warm-start vs PEFT/LoRA walkthrough page with interactive LoRA widget."""
    return request.app.state.templates.TemplateResponse(  # type: ignore[no-any-return]
        request,
        "archetypes/concept.html",
        {"steps": WARMSTART_VS_LORA_STEPS, **_arc_context("warmstart-vs-lora")},
    )

@router.get("/learn/finetune-vs-prompt-vs-rag", response_class=HTMLResponse)
async def finetune_vs_prompt_vs_rag_page(request: Request) -> HTMLResponse:
    """Render the fine-tune vs prompt vs RAG decision walkthrough page."""
    return request.app.state.templates.TemplateResponse(  # type: ignore[no-any-return]
        request,
        "archetypes/concept.html",
        {"steps": FINETUNE_VS_PROMPT_VS_RAG_STEPS, **_arc_context("finetune-vs-prompt-vs-rag")},
    )
```

### Step 4: Create LoRA Widget

New file: `anvil/api/static/js/widgets/lora.js`

Follow the existing widget pattern. **Use `governance.js` or `memory-divergence.js` as the precedent** — both are purely client-side widgets with NO `fetch`/`apiFetch` calls (proves a no-API widget works):
- IIFE exposing `window.LoraWidget`
- Constructor `LoraWidget(container)` receives the `.concept-widget` DOM element
- `_render()` builds HTML: slider for rank `r`, canvas for matrix visualization
- `_draw()` renders: original matrix W, low-rank approximation A×B, difference heatmap
- Accept `window.AnvilBase` utilities (`token()`, `initReducedMotion()`, `stop()`)
- No backend API calls — works with synthetic random matrices

**How the widget connects to the page** (no manual wiring needed): the `WARMSTART_VS_LORA_STEPS` steps carry `"widget": "lora"`. The `concept.html` template loop (lines 26-36) emits one `<div class="concept-widget" data-widget="lora"></div>` per unique widget type, and the inline init script (lines 109-116) calls `new WIDGET_CLASSES["lora"](el)` automatically.

**Widget behavior**:
- Default matrix: random 32×32
- Slider: rank `r` from 1 to 16 (default 4)
- Left panel: original matrix W (static)
- Center panel: approximation A×B (changes with rank)
- Right panel: difference heatmap (error = |W - AB|)
- Show reconstruction error as numeric value

### Step 5: Register Widget in Template

File: `anvil/api/templates/archetypes/concept.html`

1. Add script include after the last widget `<script>` (after line 86, before the nonce'd inline `<script>` at line 87):
   ```html
   <script src="/static/js/widgets/lora.js"></script>
   ```
   (External script — no CSP nonce needed; the nonce only applies to the inline block.)
2. Add to `WIDGET_CLASSES` map (lines 90-107):
   ```javascript
   lora: window.LoraWidget,
   ```

### Step 6: Add Widget CSS

File: `anvil/api/static/css/components.css`

Add `.lora-*` classes:
- `.lora-controls` — slider + label row
- `.lora-canvas` — canvas for matrix visualization
- `.lora-info` — rank/error display row
- `.coming-soon-badge` — inline badge for unshipped capabilities

## Verification

1. Start server: `make run`
2. Open `/v1/learn` — verify 3 new entries appear between "Model Export" and "Chunking Strategies"
3. Open each new page — verify prev/next navigation works
4. Open `/v1/learn/warmstart-vs-lora` — verify LoRA widget renders with slider
5. Run tests: `make test` — must pass unmodified (SC-004 NMRG)
6. Run lint: `make lint` — must pass (no new Python code beyond step arrays and routes)