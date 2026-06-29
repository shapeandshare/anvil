---
title: FAQ Accordion Passes UX-Lint With Suppression Annotations
type: discovery
tags:
  - type/discovery
  - domain/ui
created: '2026-06-28'
updated: '2026-06-28'
status: draft
code-refs:
source: agent
aliases: FAQ accordion pattern passes ux-lint with suppression annotations
---

# FAQ Accordion Passes UX-Lint With Suppression Annotations

The `faq-item` accordion pattern uses `<div onclick="toggleFaq(this)">` which
triggers the S4 "use &lt;button&gt; for actions" rule in `ux_lint.py`. However,
the pattern is keyboard-accessible via:

- `tabindex="0"` and `role="button"` on the `<div>`
- `faq-common.html` partial that adds Enter/Space key handlers
- `aria-expanded` attribute for screen reader state

The ux_lint.py tool supports line-level suppression via
`{# ux-lint:allow-next ... #}` and `{# ux-lint:allow ... #}` annotations.
The architecture-differences template uses these with justifications
referencing the keyboard support in `faq-common.html`.

**Pattern**:
```html
{# ux-lint:allow-next keyboard support via faq-common.html #}
<div class="faq-item" onclick="toggleFaq(this)" tabindex="0" role="button" aria-expanded="false">
```