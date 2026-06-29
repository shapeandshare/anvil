---
title: Spec 041 HuggingFace Model Browser UI Not Implemented
type: discovery
tags:
  - type/discovery
  - domain/content
created: '2026-06-28'
updated: '2026-06-28'
status: draft
code-refs:
source: agent
aliases: Spec 041 HuggingFace Model Browser UI not yet implemented
---

# Spec 041 HuggingFace Model Browser UI Not Implemented

The 041 (HuggingFace Model Browser) API endpoints exist (`/v1/models/external`,
`/v1/models/external/{model_id}`) and return `runnable_status` / `runnable_reason`
fields, but no UI template renders them. The external model browser page has not
been built.

As a result, the cross-link emission side of FR-025a ("cross-link FROM 041
catalog eligibility flags TO 049 architecture-differences module") cannot be
placed on the actual external model detail page. The T016 implementation placed
a banner CTA on `models.html` (the existing model registry page) linking to
`/v1/learn/architecture-differences#allow-list` — the closest equivalent for
users browsing models.

**Implication**: When the 041 browser UI is eventually implemented, it should
include a conditional "Why can't I run this?" link pointing to
`/v1/learn/architecture-differences#allow-list` on models with
`runnable_status: "track_only"`.