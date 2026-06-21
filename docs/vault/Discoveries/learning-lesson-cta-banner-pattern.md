---
title: Learning Lesson CTA Banner Pattern
type: discovery
source: agent
code-refs:
  - anvil/api/static/css/archetypes.css
  - anvil/api/templates/datasets.html
tags:
  - type/discovery
  - domain/ui
  - domain/content
created: '2026-06-20T00:00:00.000Z'
updated: '2026-06-20T00:00:00.000Z'
aliases:
  - Learning Lesson CTA Banner Pattern
---
# Learning Lesson CTA Banner Pattern

**Found**: 2026-06-20
**Context**: Moving "Understanding Datasets & Corpora" into the learning arc created a need for a lightweight CTA on the datasets page to lead users to it. The pattern generalized across 5 other pages.

## The Pattern

Every operational page SHOULD have a `.section-card--banner` at the top that cross-references its related learning lesson:

```html
<div class="section-card section-card--banner" style="--stagger-i: 0">
  <div class="section-card__content" style="display:flex;align-items:center;gap:var(--space-3);">
    <span style="font-size:1.2rem;flex-shrink:0;">📖</span>
    <div style="flex:1;">
      <div style="font-family:var(--font-body);font-weight:600;font-size:var(--text-footnote);color:var(--text-secondary);">
        How &lt;Thing&gt; Works
      </div>
      <div style="font-size:var(--text-caption-2);color:var(--text-tertiary);margin-top:2px;">
        &lt;One-line description&gt; &amp;mdash; now in the interactive learning arc.
      </div>
    </div>
    <a href="/v1/learn/&lt;lesson-key&gt;" class="btn btn-secondary btn-sm" style="flex-shrink:0;white-space:nowrap;">
      Learn More &rarr;
    </a>
  </div>
</div>
```

## CSS

Defined in `archetypes.css`:

```css
.section-card--banner {
  background: linear-gradient(135deg, color-mix(in srgb, var(--accent) 6%, var(--surface)), var(--surface) 70%);
  box-shadow: none;
  padding: var(--space-3) var(--space-4);
}
```

Key design decisions:
- **Gradient bg** — subtle accent wash distinguishes it from solid-`--surface` operational cards without competing
- **No shadow** — keeps it visually flat and receded
- **Compact padding** — `var(--space-3) var(--space-4)` vs the default card's `var(--space-6) var(--space-5)`
- **Secondary btn-sm** — muted button that doesn't compete with primary actions on the page
- **One-line description** — tight prose, "now in the interactive learning arc" tagline

## Stagger Sequencing

The banner uses `--stagger-i: 0`. Existing section-cards below must be incremented by 1 to maintain animation cadence:

```diff
- <div class="section-card" style="--stagger-i: 0">
+ <div class="section-card section-card--banner" style="--stagger-i: 0">
+ ...
+ <div class="section-card" style="--stagger-i: 1">
```

## When to Add

When a new learning lesson is added, check which operational page it relates to and add a banner. The mapping established so far:

| Page | Learning Lesson |
|------|----------------|
| `/v1/datasets-page` | `/v1/learn/data-fundamentals` |
| `/v1/training-page` | `/v1/learn/training-loop` |
| `/v1/inference-page` (playground) | `/v1/learn/sampling` |
| `/v1/models-page` | `/v1/learn/export` |
| `/v1/experiments-page` | `/v1/learn/loss` |
| `/v1/operations-page` | `/v1/learn/cloud-compute` |

## References

- `.section-card--banner` in `anvil/api/static/css/archetypes.css`
- Session log: `Sessions/2026-06-20-data-fundamentals-learning-lesson.md`
