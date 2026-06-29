---
title: Compute Resource Detection Gap for Eligibility
type: discovery
tags:
  - type/discovery
  - domain/inference
  - domain/architecture
status: reviewed
source: agent
code-refs:
  - anvil/services/compute/resolve.py
  - anvil/gpu.py
  - anvil/services/inference/model_browser.py
created: 2026-06-28
updated: 2026-06-28
aliases:
  - Compute Resource Detection
  - Eligibility Detection Constraint
---

# Compute Resource Detection Gap for Eligibility

## Discovery

The initial spec 041 (HuggingFace Model Browser) claimed that host resource
detection for model eligibility could reuse `anvil/services/compute/resolve.py`
via a `workbench.compute.device` property.  During codebase verification this
claim was found to be false on three counts:

1. **`resolve.py` returns only a device TYPE** (``DeviceType`` — ``cpu``,
   ``cuda``, ``mps``), not memory quantities.  The eligibility algorithm
   requires RAM in GB and VRAM per backend.
2. **No ``workbench.compute`` property exists** on ``AnvilWorkbench``.  The
   compute subsystem is stateless resolution functions, not a service.
3. **No per-backend VRAM detection exists for MPS** — only a unified-system-RAM
   proxy via ``psutil.virtual_memory()``.

## Resolution

The actual detection sources used instead (all confirmed to exist):

| Requirement | Source | Type |
|-------------|--------|------|
| GPU backend + VRAM | ``anvil/gpu.py:detect_gpu()`` returning ``GpuInfo`` | Core module (``anvil.gpu``) |
| System RAM | ``psutil.virtual_memory().total / (1024**3)`` | Core dependency (``psutil>=5.9``) |
| Device type | ``GpuInfo.backend`` (derived from ``detect_gpu()``) | Derived from gpu module |

The eligibility function is a pure static method:

```python
ModelBrowserService.check_eligibility(envelope, gpu, ram_total_gb) -> bool
```

MPS VRAM is explicitly documented as best-effort (unified memory proxy), and
CPU-only hosts skip the VRAM check entirely.

## Implications

- Future features that need host resource detection should use ``detect_gpu()``
  + ``psutil`` directly, not ``services/compute/resolve.py``.
- ``resolve.py`` remains useful only for device-type dispatch (which compute
  backend to select for training), not for resource quantity queries.
- If a future feature needs available (not total) RAM, it should use
  ``psutil.virtual_memory().available`` — this is already used in
  ``health_ops.py`` but not exposed through a shared service.

## Related

- [[Specs/041 HuggingFace Model Browser/041 HuggingFace Model Browser|041 HuggingFace Model Browser]]
- [[Decisions/ADR-041-simplicity-first-boring-technology|ADR-041: Simplicity First]]
