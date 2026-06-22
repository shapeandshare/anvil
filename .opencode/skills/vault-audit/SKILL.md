---
name: vault-audit
description: Run vault audit (mechanical + graph health), scope findings, plan remediation, create tasks, and fix issues. Use when asked to "audit the vault", "check vault health", "fix vault issues", "run vault-audit", "remediate vault findings", or before vault changes. Five-phase workflow: scope → audit → plan → task → remediate.
argument-hint: [--fast] [--dir <vault-path>]
---

# Vault Audit

Five-phase workflow for vault integrity management.

## Phase 0 — Preflight (always run)

1. Verify the venv is active: run `make setup` if `.venv/` is missing or stale.
2. Confirm `anvil-vault` is on PATH (it's installed as a console_scripts entry point by the package). If not: `uv sync` or `pip install -e .`.
3. Confirm the vault directory exists at `docs/vault/` (or the custom path passed via `$ARGUMENTS`).

## Phase 1 — Scoping

Determine what to audit and how:

| Question | Decision |
|----------|----------|
| Full audit or fast? | **Fast** (`--skip-graph-health`) skips networkx graph analysis — use for quick frontmatter/wikilink checks |
| Custom vault path? | Pass `--dir <path>` in `$ARGUMENTS` to override `docs/vault` |
| Remediate or just report? | **Report-only** (default), **diff** (`--diff`), or **apply** (`--apply`) |

If `$ARGUMENTS` contains `--fast`, use fast mode (skip graph health).
If `$ARGUMENTS` contains `--dir <path>`, use that vault directory.

## Phase 2 — Audit Execution

Run the audit and capture findings.

### Step 2a: Run mechanical audit

```
make vault-audit
```

Or invoke directly:
```
anvil-vault audit --vault-dir docs/vault
```

For fast mode (skip graph health):
```
make vault-audit-fast
```
or:
```
anvil-vault audit --vault-dir docs/vault --skip-graph-health
```

**What the mechanical audit checks:**

| Check | Rule | Severity | Auto-fixable |
|-------|------|----------|--------------|
| Missing frontmatter | `missing_frontmatter` | WARN | No |
| Missing required field (`title`, `type`, `tags`, `created`, `updated`) | `missing_required_field` | ERROR | Via `--apply` |
| Missing `type/*` tag | `missing_type_tag` | ERROR | Via `--apply` |
| Invalid type tag (not in controlled vocabulary) | `invalid_type_tag` | ERROR | No |
| Multiple `type/*` tags | `multiple_type_tags` | ERROR | No |
| Invalid status tag | `invalid_status_tag` | ERROR | No |
| Invalid domain tag | `invalid_domain_tag` | ERROR | No |
| Agent note missing `aliases` | `missing_aliases` | ERROR | No |
| Agent note missing `source` | `missing_source` | ERROR | No |
| Decision/discovery missing `code-refs` | `missing_code_refs` | ERROR | No |
| Invalid date format (created/updated) | `invalid_date` | ERROR | No |
| Broken wikilink (target doesn't exist) | `broken_wikilink` | ERROR | No |

### Step 2b: Preview auto-fixes

```
make vault-audit-diff
```
or:
```
anvil-vault audit --vault-dir docs/vault --diff
```

This shows exactly what `--apply` would change, without writing.

### Step 2c: Run graph health (if not fast mode)

The graph health pass runs automatically via `make vault-audit`. It produces:

- **Connectivity**: orphans (no inbound links), dead ends (no outbound links), link density, largest component size, bidirectional ratio
- **Topology**: PageRank, betweenness bridges, Louvain communities, information sinks
- **Hygiene**: tag conformity, frontmatter completeness, phantom links
- **Temporal**: stale notes (not updated >180d), temporal coherence
- **Structural**: chain gaps, potential silos, broken cycles
- **Health Score**: weighted composite 0-100

### Step 2d: Collect the findings

Read the output. Capture:
- **Error count** and **warning count** from mechanical audit
- **Health score** from graph health analysis
- **Specific findings** with file paths and rule IDs

## Phase 3 — Planning

Prioritize findings by severity and fixability:

### Priority tiers

| Tier | Type | Action |
|------|------|--------|
| **P0** | ERROR — broken wikilinks | Fix immediately. Broken links are content rot. |
| **P1** | ERROR — missing required fields / invalid tags | Fix via `--apply` or manually. Frontmatter compliance. |
| **P2** | ERROR — agent notes missing aliases/source/code-refs | Add per-note. Required for agent accountability. |
| **P3** | WARN — missing frontmatter | Add frontmatter if the note is active. Consider archiving if abandoned. |
| **P4** | Graph health — orphans, dead ends, sinks | Assess each. Some are legitimate (MOCs, session logs). Flag true orphans. |
| **P5** | Graph health — low coherence, stale notes | Human-only. Requires context to resolve. |
| **P6** | Graph health — structural gaps, missing links | Link prediction suggestions. Review each before adding. |

### Decide remediation mode

- **Safe auto-fixes only**: `make vault-audit-apply` — handles missing dates, tag casing, aliases
- **Manual fixes**: broken wikilinks, invalid tags, missing frontmatter
- **Guided fixes**: graph health issues — each requires judgment

## Phase 4 — Tasking

Create tracked todo items for remediation. Group by:

1. **Auto-fix batch** (1 todo): Apply `--apply` mode
2. **Broken wikilinks** (per affected file, grouped): Fix or create target notes
3. **Frontmatter issues** (per affected file): Add missing fields, fix invalid tags
4. **Agent note metadata** (per affected file): Add `aliases`, `source`, `code-refs`
5. **Graph health items** (grouped by sub-type): Orphans, dead ends, sinks, coherence
6. **Stale notes** (per affected file, if auto-detected): Review and clear staleness
7. **Final verification** (1 todo): Re-run audit to confirm 0 errors

Key tasking principles:
- Each todo is one atomic action (one file fix, one batch apply, one verification run)
- Order: auto-fix first (clears noise), then real issues
- Group scattered fixes on the same file into a single todo

## Phase 5 — Remediation

### Step 5a: Apply auto-fixes

```bash
make vault-audit-apply
```

This fixes:
- Missing date fields (injects `created`/`updated` with current date)
- Tag casing (normalizes to controlled vocabulary)
- Missing `aliases` field on agent notes

If you want to review changes first:
```bash
make vault-audit-diff
```

### Step 5b: Fix broken wikilinks

For each `broken_wikilink` finding:
1. **Target note exists under a different name?** Update the wikilink to use the correct stem.
2. **Target note should exist?** Create the note with proper frontmatter.
3. **Link is stale/deprecated?** Remove or comment the wikilink.

Vault conventions to follow when creating notes:
- Frontmatter: `title`, `type`, `tags` (from `docs/vault/_meta/tags.md`), `created`, `updated`
- Agent notes (decision/discovery/session-log) also need: `aliases`, `source`, and `code-refs` (decision/discovery only)
- Status tags: one of `status/draft`, `status/wip`, `status/reviewed`, `status/canonical`, `status/superseded`
- Type tags: exactly one of `type/principle`, `type/design`, `type/system`, `type/reference`, `type/moc`, `type/decision`, `type/discovery`, `type/session-log`

### Step 5c: Fix frontmatter issues

For each finding, edit the file's YAML frontmatter:
- Add missing required fields (`title`, `type`, `tags`, `created`, `updated`)
- Replace invalid tags with valid ones from `docs/vault/_meta/tags.md`
- Fix date formats (use ISO 8601: `YYYY-MM-DD`)
- Remove duplicate or conflicting `type/*` tags

### Step 5d: Fix agent note metadata

For `missing_aliases`, `missing_source`, `missing_code_refs`:
- If the note was created by an agent (decision/discovery/session-log), add the missing fields
- `aliases`: a list of alternative names for wikilink resolution
- `source`: the agent session or trigger that produced this note
- `code-refs`: (decision/discovery only) list of file paths cited

### Step 5e: Address graph health findings

For **orphans** and **dead ends**:
- Add inbound/outbound wikilinks where appropriate
- MOCs and session logs are exempt from orphan status — these are expected
- If a note is truly isolated with no purpose, consider archiving

For **information sinks** (high in-degree, zero out-degree):
- Add outbound wikilinks to related notes
- Reference sources, dependencies, and related topics

For **communities needing MOC**:
- If a community of ≥5 notes lacks a MOC, create a Map of Content note

For **missing reciprocal links**:
- If A links to B but B doesn't link back, verify B should link to A and add it

### Step 5f: Verify

Re-run the audit:

```bash
make vault-audit
```

Confirm 0 errors. If using graph health, confirm the health score improved.

## References

- `docs/vault/Systems/Vault Health.md` — System documentation
- `docs/vault/_meta/tags.md` — Controlled tag vocabulary
- `shared/vault.mk` — Makefile targets
- `anvil/services/vault/cli.py` — CLI entry point (`anvil-vault`)
- `anvil/services/vault/vault_audit.py` — Mechanical audit service
- `anvil/services/vault/vault_health_service.py` — Audit orchestrator
- `anvil/services/vault/scanner.py` — Graph health analyzer
- `anvil/services/vault/_types.py` — Finding, MechanicalReport, GraphHealthReport types