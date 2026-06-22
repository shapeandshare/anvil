---
name: ux-generate
description: Generate UI code (Jinja templates, HTML, CSS) that complies with the repo's UX rules (docs/ux-rules.md). Treat S4 and S3 rules as hard constraints. Applies when agent creates or edits templates, HTML, or CSS files.
argument-hint: <prompt-for-ui-code>
---

# UX generation

1. Read the ruleset from the repo: **`docs/ux-rules.md`**. It holds the operating
   contract, severity model, enforceability, dedup precedence, rules, and output
   contract — authoritative; they override anything below on conflict.
2. Treat all **S4** and **S3** rules as hard constraints during generation:
   - Never write unsafe `|safe` without justification + `ux-lint:allow` annotation.
   - Use `<button>` for actions, `<a>` for navigation — never `<div>`/`<span>` with click handlers.
   - Always include CSRF tokens on state-changing forms.
   - Coalesce SSE `aria-live` announcements to milestones — never per-chunk.
   - Always include visible focus indicators; never `outline: none` without replacement.
   - Honor `prefers-reduced-motion` for animations.
3. Apply **Server-render** owned rules: autoescaping ON, secrets never in template context.
4. Apply **Streaming** owned rules: milestone-based `aria-live="polite"`, connection-state indicator.
5. Apply **Terminal aesthetic** owned rules: keyboard-first, effective contrast before bloom overlay,
   state never signaled by color/glow alone.
6. S2/S1 rules are guidance — apply where practical without over-engineering.
7. Review your own output: if any S4/S3 violation remains, flag it as a warning for human review.