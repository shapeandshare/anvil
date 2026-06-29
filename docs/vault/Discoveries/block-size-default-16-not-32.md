---
title: Default block_size is 16, not 32
type: discovery
tags:
  - type/discovery
  - domain/core
created: '2026-06-28'
updated: '2026-06-28'
status: draft
code-refs:
source: agent
aliases: Default block_size is 16 not 32
---

# Default block_size is 16, not 32

The anvil engine's default context window (`block_size`) is **16** tokens, set
in `anvil/core/engine.py:114`:

```python
block_size: int = 16,
```

An early draft of the spec 049 content claimed "max context 32". This was
factually incorrect. The correct value is 16.

**Lesson**: Always verify numeric claims against the code single source of truth
before writing teaching content. Added a verification gate in FR-032 and T006
requiring taught values to match the codebase.