---
title: ADR-039: Spec Migration to Vault
type: decision
tags:
  - type/decision
  - domain/vault
  - domain/governance
created: 2026-06-22
updated: 2026-06-22
aliases:
  - ADR-039 Specs to Vault
---

# ADR-039: Migrate `specs/` Artifacts into `docs/vault/Specs/`

**Status:** Accepted

**Context:** The `specs/` directory at the repo root held feature specifications (spec.md, plan.md, tasks.md, research.md, data-model.md, quickstart.md) alongside scaffold subdirectories (checklists/, contracts/). These artifacts were the only major documentation surface outside the Obsidian vault at `docs/vault/`. They were not discoverable from the knowledge graph, not linked to Systems/ or Code/ notes, and not subject to vault audit rules (frontmatter validation, wikilink integrity, graph-health analysis).

oldgrowth proved the model of co-locating specs inside the vault as first-class graph nodes carrying `type/spec` with frontmatter, `spec-refs:`, and wikilinks outward to implementing notes.

**Decision:** Move all 25 spec directories from `specs/` into `docs/vault/Specs/NNN Title/` and delete `specs/`.

- Each spec becomes a subdirectory `docs/vault/Specs/NNN Title/` containing a root index note (`NNN Title.md` with full frontmatter) and prefixed artifact files (`NNN Title - plan.md`, etc.).
- Artifact files receive injected YAML frontmatter (`type/spec` tag, `created: ~` null dates) so the vault audit passes cleanly.
- Scaffold subdirectories (`checklists/`, `contracts/`) are moved as-is with no frontmatter; the audit skips them.
- The spec-kit toolchain (`.specify/scripts/bash/common.sh`, `.specify/feature.json`, templates, git extension) is rewired to resolve paths under `docs/vault/Specs/`.
- A new `anvil-vault migrate-specs` CLI subcommand with `--dry-run`/`--verify-only`/`--apply` modes supports the migration (TDD'd, mypy strict, 53 unit tests).
- The vault audit and graph-health scanner were extended with `_is_scaffold_path` and `_is_spec_subfile` exemption logic (ported from oldgrowth) so spec artifacts don't flood audit findings.

**Consequences:**

- Positive: All 460 notes in the vault are now graph-resident, auditable, and wikilinkable. Specs link forward to Systems/ and Code/ notes.
- Positive: `anvil-vault migrate-specs` is reusable for any future spec-to-vault migrations.
- Negative: New specs created by the spec-kit workflow now land in `docs/vault/Specs/` with kebab-case names (branch-derived), needing a manual rename to Title Case until the create-new-feature scripts are updated to produce Title Case dirs.
- Risk: The `.specify/feature.json` path now contains a space (`docs/vault/Specs/025 UX Rules Integration`); all consumers quote the path (confirmed by auditing `get_feature_paths` in `common.sh`).

**References:**
- [[Specs/Specs]] — folder MOC for vault specs
- [[Systems/Vault Structure]] — updated vault layout
- [[Systems/Vault Health]] — audit tooling with spec-aware exclusions
- oldgrowth `scripts/ci/migrate_specs_to_vault.py` — original pattern (not directly reusable—anvil has no `specs/INDEX.md`)

## Change Log

- 2026-06-22: Initial ADR.
