---
title: Quickstart — Learning Architecture Differences
type: spec
tags:
  - type/spec
created: '2026-06-28'
updated: '2026-06-28'
---
# Quickstart: Learning Architecture Differences

## Implementation Steps

All changes are within or alongside existing files. No new Python modules, database migrations, or configuration.

### Step 1: Create Accordion Template

New file: `anvil/api/templates/archetypes/architecture-differences.html`

A Jinja2 template extending `base.html` that:
- Reuses `.concept-lesson-header` for arc navigation (prev/next, "Back to Learning Index")
- Reuses `.section-card` from archetypes.css for section card styling
- Reuses `.faq-item`, `.faq-question`, `.faq-answer`, `.faq-toggle` from components.css for accordion behavior
- Reuses `toggleFaq()` from `archetypes/faq.html` partial for accordion toggle logic (inline the function or include via partial)
- Has inline JS to auto-open the section matching `window.location.hash` on page load
- Each accordion section uses `<div id="{{ step.key }}">` for anchor targeting

Template structure:
```html
{% extends "base.html" %}
{% block extra_css %}<link rel="stylesheet" href="/static/css/archetypes.css">{% endblock %}
{% block content %}
<div class="concept-lesson">
  {% if arc %}
  <div class="concept-lesson-header">
    <h1 class="concept-lesson-title">{{ arc[current_index].title }} <span class="lesson-count">&mdash; Lesson {{ current_index + 1 }} of {{ arc|length }}</span></h1>
    <nav class="learn-arc-nav" aria-label="Lesson navigation">
      <div class="learn-arc-links">
        <a href="/v1/learn" class="btn btn-secondary">&larr; Back to Learning Index</a>
        {% if prev %}
        <a href="{{ prev.path }}" class="btn btn-secondary">&larr; {{ prev.title }}</a>
        {% endif %}
        {% if next %}
        <a href="{{ next.path }}" class="btn btn-secondary">{{ next.title }} &rarr;</a>
        {% endif %}
      </div>
    </nav>
  </div>
  {% endif %}

  <!-- Introduction paragraph -->
  <p class="page-intro" style="margin: var(--space-4) auto; max-width: 640px;">...</p>

  <!-- Accordion sections -->
  <div style="max-width: 640px; margin: 0 auto;">
    {% for step in steps %}
    <div class="faq-item section-card" id="{{ step.key }}" onclick="toggleFaq(this)" tabindex="0" role="button" aria-expanded="false">
      <div class="faq-question section-card__header">
        <span class="section-card__title">{{ step.title }}</span>
        <span class="faq-toggle">[+]</span>
      </div>
      <div class="faq-answer section-card__content" style="display: none;">
        {{ step.body | safe }}
      </div>
    </div>
    {% endfor %}
  </div>
</div>
{% endblock %}
{% block scripts %}
<script nonce="{{ request.state.csp_nonce }}">
/* ── Accordion toggle (same pattern as faq.html) ── */
function toggleFaq(el) {
  var expanded = el.getAttribute('aria-expanded') === 'true';
  el.setAttribute('aria-expanded', !expanded);
  var answer = el.querySelector('.faq-answer');
  var toggle = el.querySelector('.faq-toggle');
  if (answer.style.display === 'none' || answer.style.display === '') {
    answer.style.display = 'block';
    toggle.textContent = '[-]';
  } else {
    answer.style.display = 'none';
    toggle.textContent = '[+]';
  }
}

/* ── Auto-open section for anchor-ID linking from 041 ── */
(function() {
  var hash = window.location.hash;
  if (hash) {
    var el = document.getElementById(hash.replace('#', ''));
    if (el && el.classList.contains('faq-item')) {
      setTimeout(function() { toggleFaq(el); }, 100);
    }
  }
})();
</script>
{% endblock %}
{% block didyouknow_banner %}
<div id="didyouknow-banner" class="didyouknow">...</div>
{% endblock %}
```

### Step 2: Add Step Data Array

File: `anvil/api/v1/learning.py` — add `ARCHITECTURE_DIFFERENCES_STEPS` after the existing 048 step arrays (after `FINETUNE_VS_PROMPT_VS_RAG_STEPS`)

```python
ARCHITECTURE_DIFFERENCES_STEPS = [
    {
        "key": "tokenization",
        "title": "Tokenization Differences",
        "body": (
            "<p>anvil's char-level mini-Llama tokenizer maps each character independently "
            "— every letter, space, and punctuation mark is one token (vocab_size = number of "
            "unique characters in the training data + BOS). Production models use subword "
            "tokenizers (BPE, Unigram, WordPiece) with vocabularies of 16K-128K tokens.</p>"
            "<p><b>Fine-tuning implications:</b> A model trained with a char-level tokenizer "
            "cannot load subword-pretrained weights. The tokenizer is baked into the embedding "
            "matrix dimensions. Adding new tokens (e.g., domain-specific terms) requires "
            "vocabulary extension or adapter-based approaches like LoRA.</p>"
        ),
    },
    {
        "key": "attention",
        "title": "Attention Variants",
        "body": (
            "<p>anvil uses full multi-head causal attention with n_head heads, each with "
            "its own Q, K, V, and O projections per layer. Production models increasingly "
            "use grouped-query attention (GQA) or multi-query attention (MQA) where "
            "multiple heads share K and V projections to reduce KV cache size at inference.</p>"
            "<p><b>Fine-tuning implications:</b> GQA/MQA weights have different tensor shapes "
            "than full multi-head attention. A checkpoint converted between architectures "
            "requires projected weight remapping. LoRA adapters are architecture-independent "
            "as long as the target module shapes match.</p>"
        ),
    },
    {
        "key": "parameters",
        "title": "Parameter Scaling",
        "body": (
            "<p>anvil's default model uses n_embd=16, n_layer=1, n_head=4 ≈ 4K parameters. "
            "TinyLlama-class models (n_embd=2048, n_layer=22, n_head=32) have ~1.1B parameters. "
            "The embedding matrix alone (vocab_size × n_embd) scales linearly; the attention "
            "projections (n_embd² per head) scale quadratically.</p>"
            "<p><b>Fine-tuning implications:</b> Parameter scale determines what fine-tuning "
            "methods are practical. Full fine-tuning of a 1B-parameter model requires ~20GB "
            "VRAM for optimizer states alone. LoRA fine-tunes < 1% of parameters per rank-8 "
            "adapter, making it feasible on consumer GPUs. Warm-start (spec 039) works at any "
            "scale because it updates the same parameter count as training.</p>"
        ),
    },
    {
        "key": "context",
        "title": "Context Length",
        "body": (
            "<p>anvil processes sequences up to the training <code>block_size</code> (default: 16 tokens). "
            "Production models support 4K-128K+ tokens of context. RoPE (Rotary Position "
            "Embedding) enables some context extrapolation — models can generalize to slightly "
            "longer sequences than trained on — but quality degrades beyond the trained range.</p>"
            "<p><b>Fine-tuning implications:</b> Fine-tuning with longer contexts requires "
            "RoPE extension (e.g., YaRN, NTK-aware scaling). The tokenizer also matters: "
            "char-level tokenizers create very long token sequences for the same text, "
            "so effective context in character tokens is much shorter than subword tokens.</p>"
        ),
    },
    {
        "key": "allow-list",
        "title": "Architecture Allow-List",
        "body": (
            "<p>anvil executes a limited, explicit set of architectures. The v1 allow-list "
            "is <b>LlamaForCausalLM</b> with <b>safetensors</b> weight files — the same "
            "format exported by anvil's own training pipeline (spec 042). This guarantee "
            "is possible because:</p>"
            "<ul>"
            "<li><b>Tokenizer compatibility:</b> Weight loading requires matching vocab_size "
            "and embedding dimensions; mismatched tokenizers must be adapted separately.</li>"
            "<li><b>Weight format:</b> safetensors is the universal exchange format — no "
            "pickle security risks, no framework-specific serialization.</li>"
            "<li><b>Architecture differences:</b> Different attention mechanisms, MLP "
            "configurations, norm placements, and position encodings require different "
            "forward-pass implementations.</li>"
            "</ul>"
            "<p>Models not in the allow-list are <b>tracked but not runnable</b> — the "
            "catalog (041) records them with eligibility flags, and this module explains "
            "why they can't execute. GGUF models (specs 050-052) are a planned, deferred "
            "type that will expand the allow-list in a future release. The architectural "
            "differences above explain why each boundary exists and what would be required "
            "to support a broader set.</p>"
        ),
    },
]
```

### Step 3: Add LEARNING_ARC Entry

File: `anvil/api/v1/learning.py` — insert after the `"finetune-vs-prompt-vs-rag"` entry (after `"desc": ...` line), before the `"chunking"` entry.

```python
{
    "key": "architecture-differences",
    "title": "Architecture Differences",
    "path": "/v1/learn/architecture-differences",
    "desc": "How model architectures differ — tokenization, attention variants, parameter scaling, context length — and what those differences mean for fine-tuning.",
},
```

### Step 4: Add Route Handler

File: `anvil/api/v1/learning.py` — add after `finetune_vs_prompt_vs_rag_page()` (after the last 048 route handler).

```python
@router.get("/learn/architecture-differences", response_class=HTMLResponse)
async def architecture_differences_page(request: Request) -> HTMLResponse:
    """Render the architecture-differences accordion page.

    Uses a custom accordion template (not the carousel ``concept.html``)
    because FR-025 UX requires expandable/collapsible sections layout.
    """
    return request.app.state.templates.TemplateResponse(  # type: ignore[no-any-return]
        request,
        "archetypes/architecture-differences.html",
        {"steps": ARCHITECTURE_DIFFERENCES_STEPS, **_arc_context("architecture-differences")},
    )
```

### Step 5: Add e2e Test

File: `tests/e2e/api/test_pages.py` — add after the 048 fine-tuning tests.

```python
@pytest.mark.asyncio
async def test_learn_architecture_differences(client: httpx.AsyncClient) -> None:
    """GET /v1/learn/architecture-differences returns 200 with expected content."""
    r = await client.get("/v1/learn/architecture-differences")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
    # Verify accordion sections exist
    assert "Tokenization Differences" in r.text
    assert "Attention Variants" in r.text
    assert "Parameter Scaling" in r.text
    assert "Context Length" in r.text
    assert "Architecture Allow-List" in r.text
    # Verify arc navigation
    assert "Fine-Tune vs Prompt vs RAG" in r.text or "Learning Index" in r.text
    assert "Chunking Strategies" in r.text
    # Verify anchor ID for cross-linking from 041
    assert 'id="allow-list"' in r.text or 'id="allow-list"' in r.text
```

### Step 6: Verify

1. Start server: `make run`
2. Open `/v1/learn` — verify "Architecture Differences" appears between "Fine-Tune vs Prompt vs RAG" and "Chunking Strategies"
3. Open `/v1/learn/architecture-differences` — verify accordion sections display and toggle correctly
4. Open `/v1/learn/architecture-differences#allow-list` — verify auto-open on allow-list section
5. Run tests: `make test` — must pass unmodified (SC-005 NMRG) + new test passes
6. Run lint: `make lint` — must pass (no new Python code beyond steps array and route)