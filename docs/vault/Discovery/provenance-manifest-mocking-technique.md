---
created: '2026-06-19'
status: draft
tags:
  - type/discovery
  - domain/tooling
  - domain/governance
  - status/draft
title: Provenance Manifest Mocking in Tests
type: discovery
updated: '2026-06-19'
aliases:
  - Provenance Manifest Mocking in Tests
source: agent
code-refs:
  - anvil/services/demo/demo_bootstrap.py
  - tests/test_bootstrap.py
  - specs/015-demo-data-bootstrap/spec.md
---
# Provenance Manifest Mocking in Tests

**Type**: discovery-note
**Tags**: testing, provenance, demo-bootstrap
**Date**: 2026-06-19

## Problem

The `DemoBootstrapService` loads its provenance manifest from the installed package resources (`_resources.files("anvil").joinpath("data", "demo", "provenance.json")`), not from the `DEMO_DIR` path. When test fixtures mock `DEMO_DIR` with `monkeypatch.setattr("anvil.services.demo.demo_bootstrap.DEMO_DIR", tmp_path)`, the provenance lookup still reads from the real package file, not the temp directory.

## Solution

Inject the provenance manifest directly into the service instance after construction:

```python
def _svc_with_provenance(session) -> DemoBootstrapService:
    svc = DemoBootstrapService(session)
    svc._provenance_manifest = {
        "small/names": {"source": "...", "license": "MIT", "attribution": ""},
        "medium/math-facts": {"source": "...", "license": "Generated/Original", "attribution": ""},
    }
    return svc
```

## Key detail

The lookup strips `.txt` suffix before matching keys: `key = rel.removesuffix(".txt")`. So manifest keys for `.txt` files should NOT include the extension. For directory-based corpora, keys use the directory path directly (e.g., `"small/names"`).

## Related

- Spec: `specs/015-demo-data-bootstrap/spec.md`
- Implementation: `tests/test_bootstrap.py::_svc_with_provenance`
