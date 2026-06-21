---
created: '2026-06-21T00:00:00.000Z'
tags:
  - type/session-log
  - domain/core
  - domain/tooling
title: input.txt Relocation to examples/
type: session-log
updated: '2026-06-21T00:00:00.000Z'
aliases: []
source: agent
---
**Date**: 2026-06-21
**Agent**: Sisyphus

## Summary

Investigated `input.txt` at the repo root — a 32K-line (~228KB) list of baby names used as a training corpus by legacy example scripts (`examples/train0.py`–`train5.py`). The main anvil application doesn't depend on it (the training pipeline uses the dataset/corpus management system). Moved it to `examples/input.txt` and updated all path references.

## Changes

| File | Change |
|------|--------|
| `input.txt` (root) | Deleted — moved to `examples/input.txt` |
| `examples/train0.py` – `train5.py` | `open("input.txt")` → `open("examples/input.txt")` |
| `anvil/api/templates/archetypes/training.html` | `"input.txt (default)"` → `"examples/input.txt (default)"` |

## Discovery

The file was already committed at `examples/input.txt` in the git tree (identical content), so the `mv` operation resulted in no additional tracking delta beyond the root deletion. Likely a previous session had staged it there but the root copy was the one being worked against.
