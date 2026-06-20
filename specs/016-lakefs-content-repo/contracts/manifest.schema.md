# Contract: Content Version Manifest (the reproducibility anchor)

**Feature**: `016-lakefs-content-repo` | **Phase 1**

A **Content Version** is identified by the `sha256` of its canonical-JSON manifest. The
manifest is the portable, self-describing reproducibility record (logged to MLflow as
`corpus_manifest.json` and anchored by `corpus_ref` = the digest).

## Canonical JSON shape

```json
{
  "schema": "anvil.content.manifest/v1",
  "corpus_slug": "shakespeare",
  "version_number": 3,
  "is_composition": false,
  "chunk_cfg": { "strategy": "windowed", "block_size": 16, "chunk_overlap": 0.5 },
  "entries": [
    { "path": "sonnets/001.txt", "content_hash": "<sha256hex>", "weight": 1.0, "source": "manual" },
    { "path": "plays/hamlet.txt", "content_hash": "<sha256hex>", "weight": 2.0, "source": "import-gutenberg" }
  ]
}
```

## Digest rule

```
entries sorted by (path, content_hash)
canonical = json.dumps(manifest, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
manifest_digest = hashlib.sha256(canonical).hexdigest()   # 64 hex chars
```

## Field rules

| Field | Rule |
|---|---|
| `schema` | constant version tag; bump only on breaking manifest changes |
| `corpus_slug` | the canonical corpus slug |
| `version_number` | monotonic per corpus (human label basis; NOT the identity) |
| `is_composition` | true iff weights/selection differ from a plain snapshot |
| `chunk_cfg` | strategy + params applied at training resolution |
| `entries[].content_hash` | sha256 of the blob bytes (content-addressed; immutable) |
| `entries[].weight` | ensemble sampling weight; default 1.0; all-zero rejected (FR-022) |
| `entries[].source` | originating source slug or null |

## Guarantees

- **Immutable (FR-004)**: any change to entries/weights/chunk_cfg changes the digest →
  a new version; existing versions never mutate.
- **Reproducible (FR-003, SC-001)**: the digest deterministically resolves to the exact
  entries → exact content-addressed blobs, independent of later corpus state.
- **Composition fidelity (FR-020/021, SC-006)**: the recipe (weights/selection) is part
  of the manifest, so re-opening reproduces the mix exactly and training applies the
  recorded weights.
- **Retention (FR-024, SC-002)**: a digest referenced by a run (or tagged) is reachable;
  its blobs are GC-protected.

## MLflow record (on run start)

```
mlflow.log_param("corpus_ref", manifest_digest)
client.log_input(run_id, dataset=MetaDataset(
    source=f"anvil-content://{corpus_slug}/{manifest_digest}",
    name=corpus_slug, digest=manifest_digest), context="corpus")
mlflow.log_dict(manifest, "corpus_manifest.json")
```
