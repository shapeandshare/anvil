# Contract: Bundled Provenance Manifest (`anvil/data/demo/provenance.json`)

Machine-readable source-of-truth for bundled sample provenance (FR-004). Mirrors the columns of the existing `anvil/data/demo/README.md` license table. Bundled in the wheel via `[tool.setuptools.package-data]` (add `data/demo/**/*.json` to the existing globs). Resolved at runtime by `DemoBootstrapService` via `importlib.resources` (the same mechanism already used to locate `data/demo`).

## Schema

```jsonc
{
  "<demo-relative-path>": {        // e.g. "medium/alice", "presidents.txt", "small/names"
    "source": "string",            // human-readable origin (e.g. "Project Gutenberg #11")
    "license": "string",           // MUST match a license_catalog.identifier (approved set)
    "attribution": "string"        // required attribution; "" when license requires none
  }
  // ... one entry per bundled corpus dir and bundled .txt dataset
}
```

## Rules
- C-M1: Every bundled demo item (each subdirectory → corpus, each top-level `.txt` → dataset) MUST have a manifest entry. A missing entry causes the item to be **not seeded** and a refusal recorded (FR-003).
- C-M2: `license` MUST resolve to an approved `license_catalog.identifier` (NOT the `own-content` sentinel). Unknown/empty → item skipped + refusal recorded (VR-P1).
- C-M3: If the resolved license has `requires_attribution=true`, `attribution` MUST be non-empty (VR-P3).
- C-M4: The manifest is read-only at runtime; it is the authoritative seed input (demo files live in a read-only installed package location).

## Expected initial entries (from current demo README)

| Key | source | license | attribution |
|---|---|---|---|
| `small/names` | Public name lists | `MIT` | (as required) |
| `small/hello-world` | Hand-crafted Python | `Generated/Original` | "" |
| `presidents.txt` | Project Gutenberg | `Public Domain` | "" |
| `medium/alice` | Project Gutenberg #11 | `Public Domain` | "" |
| `medium/math-facts.txt` | Hand-crafted | `Generated/Original` | "" |
| `large/earnest` | Project Gutenberg #844 | `Public Domain` | "" |

> Exact `source`/`attribution` strings to be transcribed verbatim from `anvil/data/demo/README.md` during implementation (the README remains the human-readable companion; the JSON is the enforced source-of-truth).

## Test obligations
- T-M1: manifest validates against schema; every key maps to an existing bundled path.
- T-M2: every `license` resolves to an approved catalog identifier.
- T-M3: bootstrap with a manifest entry removed → that item is skipped and a refusal audit/reason recorded.
- T-M4: attribution-required license with empty attribution → schema/seed validation fails.
