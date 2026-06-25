---
title: 'Session: Panel Spacing Tweak'
type: session-log
tags:
  - type/session-log
  - domain/ui
created: '2026-06-14'
updated: '2026-06-14'
aliases:
  - 2026-06-14-panel-spacing-tweak
source: agent
---
# Session: Panel Spacing Tweak

**Date**: 2026-06-14
**Status**: Completed

## Summary

Increased vertical spacing between `.section-card` "boxes" on all pages from `var(--space-1)` (4px) to `var(--space-4)` (16px) for better visual breathing room.

## Changes

- **File**: `anvil/api/static/css/archetypes.css`
- **Rule**: `.section-card` → `margin-bottom` → `var(--space-4)` (was `var(--space-1)`)
- **Pages affected**: datasets, experiments, operations, playground, graph, models, faq pages (18 instances across 9 templates)
- **Not affected**: Training dashboard (has `.training-dashboard .section-card { margin-bottom: 0 }` override — already uses `gap: var(--space-4)`)

## Context

User request: "the boxes on all tha pages need more space between each other."

The universal "box" component was identified as `.section-card` — the iOS-style card used as the primary content container across every page. The existing 4px gap was too tight, making stacked sections feel cramped.