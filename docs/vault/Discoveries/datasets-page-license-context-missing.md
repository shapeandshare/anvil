---
aliases:
  - 'Datasets Page License Dropdown Missing Template Context'
code-refs:
  - anvil/api/v1/pages.py
  - anvil/api/templates/datasets.html
  - anvil/api/v1/governance.py
created: '2026-06-19'
source: agent
status: draft
tags:
  - type/discovery
  - domain/governance
  - domain/ui
title: 'Datasets Page License Dropdown Missing Template Context'
type: discovery
updated: '2026-06-19'
---

# Discovery: Datasets Page License Dropdown Missing Template Context

## What was found

The `datasets.html` template renders a `<select id="license-select">` dropdown
that iterates over a `licenses` Jinja2 context variable with
`{% for license in licenses %}`. The `datasets_page` handler in
`anvil/api/v1/pages.py` called `TemplateResponse("datasets.html")` with no
context at all, so `licenses` was never provided and the dropdown rendered as
empty (only the default "Select a license..." option).

This is a governance feature integration gap: the license catalog was
seeded by `GovernanceService.seed_catalog()` at startup and exposed via
`GET /v1/governance/licenses`, but the page template was never wired to
fetch and pass the catalog.

## Impact

Users could not select a license from the dropdown when uploading a dataset.
The provenance and governance fields in the upload form were effectively
non-functional — the dropdown appeared empty.

## Resolution

The `datasets_page` handler now accepts `Depends(get_workbench)`, calls
`workbench.governance.list_licenses(include_own_content=False)`, and passes
the result as `{"licenses": licenses}` to the template. The template was also
updated to use `license.identifier` for option values and
`license.display_name` for visible labels (previously it used `{{ license }}`
which would render the object repr).

## Prevention

Any page template that renders the governance license dropdown must
receive `licenses` in its template context. A pattern to watch for:
`TemplateResponse(request, "*.html")` calls with no third argument (empty
context) are a red flag when the template iterates over server-side data.

## References

- `anvil/api/v1/pages.py` — `datasets_page()` handler
- `anvil/api/templates/datasets.html` — `#license-select` dropdown
- `anvil/api/v1/governance.py` — `GET /v1/governance/licenses` API endpoint
