---
aliases:
  - Vault Audit Forward Wikilink Resolution Bug
code-refs:
  - anvil/services/vault/vault_audit.py
  - tests/services/vault/test_vault_audit.py
created: '2026-06-19'
related:
  - '[[Systems/Systems]]'
session: 2026-06-19-cms-landscape-report
source: agent
status: draft
summary: >-
  Mechanical audit populated its filename index incrementally inside the
  wikilink-validation loop, producing false broken-link errors for forward
  (alphabetically-later) link targets. Fixed by pre-building the full index.
tags:
  - type/discovery
  - domain/tooling
  - status/draft
title: Vault Audit Forward Wikilink Resolution Bug
type: discovery
updated: '2026-06-19'
---
The vault mechanical audit reported false `broken_wikilink` errors whenever a note linked to another note whose filename sorted alphabetically *after* it.

The root cause was in the synchronous mechanical-audit loop. The `filename_index` (mapping note stem → path, used to resolve wikilink targets) was populated **incrementally inside the same loop** that validated wikilinks. Because `sorted(rglob("*.md"))` yields files in alphabetical order, any note linking forward to a not-yet-iterated target had that target reported as missing. For example, `ContentManagementLandscape.md` links to `TrainingDataFlow`, `MlflowIntegration`, and `InfraParadigms`, all of which sort later — so all three were spuriously flagged. The same bug affected ~10 canonical notes vault-wide (every note linking to `TrainingDataFlow`, plus several ADRs).

A correct `build_filename_index()` helper already existed on the service but was unused by the audit path. The fix pre-builds the complete `filename_index` (applying the same `_meta`/`.obsidian`/`addons` exclusions) in a first pass before the wikilink-validation pass, making resolution independent of iteration order. After the fix, vault-wide spurious broken-link errors dropped to 3 genuinely-missing ADR targets in an unrelated note. A regression test (`test_forward_wikilink_resolves`) creates an `Aaa → Zzz` forward link and asserts no broken-link finding.

Note for future agents: until this fix, the conventional advice "use full `[[Reference/Note|alias]]` paths" did **not** help, because the resolver strips the directory prefix (`wl.rsplit("/", 1)[-1]`) and matches on bare stem regardless. The real fix had to be in the resolver, not in link formatting.

## References
- [[Discoveries/Discoveries|Discoveries]]

- `anvil/services/vault/vault_audit.py` — `_run_mechanical_audit_sync` (index pre-build), `build_filename_index`
- `tests/services/vault/test_vault_audit.py` — `test_forward_wikilink_resolves`
