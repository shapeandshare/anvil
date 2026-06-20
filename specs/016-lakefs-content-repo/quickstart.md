# Quickstart: Content Repository (local mode)

**Feature**: `016-lakefs-content-repo` | **Phase 1**

Validates the P1 vertical slice end-to-end: **create corpus → ingest → validate → freeze
version → pin in a training run → re-resolve identically**. Local mode is fully
self-contained (no LakeFS, no object store, no extra services — pure Python over the
existing filesystem + SQLite, per research D1).

## Prerequisites

```bash
make setup     # venv + deps (no new runtime deps for local mode)
make run       # web + MLflow; the content repository is built-in, zero config
```

There is **nothing to install or configure** for the content repository — no LakeFS, no
MinIO, no credentials (US8 / FR-039/040).

## 1. Register a source and create a corpus

```bash
curl -s -X POST localhost:8080/v1/content/sources \
  -H 'content-type: application/json' \
  -d '{"slug":"manual","name":"Manual uploads","kind":"manual"}'

curl -s -X POST localhost:8080/v1/content/corpora \
  -H 'content-type: application/json' \
  -d '{"name":"Shakespeare","declared_source":"Project Gutenberg",
       "license":"Public Domain","chunking_strategy":"windowed",
       "block_size":16,"chunk_overlap":0.5}'
# → {"data":{"id":1,"slug":"shakespeare",...},"error":null}
```

## 2. Open an isolated ingest session and stage content

```bash
SID=$(curl -s -X POST localhost:8080/v1/content/sessions \
  -H 'content-type: application/json' \
  -d '{"corpus_id":1,"source":"manual"}' | jq -r .data.id)

curl -s -X POST localhost:8080/v1/content/sessions/$SID/stage \
  -F 'path=sonnets/001.txt' -F 'file=@sonnet1.txt'
```

## 3. Validate (fast per-batch gate, ~5s) and accept (atomic fold → new version)

```bash
curl -s -X POST localhost:8080/v1/content/sessions/$SID/validate
# → {"data":{"ok":true,"problems":[]},"error":null}

curl -s -X POST localhost:8080/v1/content/sessions/$SID/accept
# → {"data":{"version_id":1,"manifest_digest":"<sha256>","version_number":1},"error":null}
```

If a gate fails, `accept` returns `422` with structured `problems`, and the canonical
corpus is **unchanged** (fail-closed, FR-014/016).

## 4. Freeze + tag a version (optional explicit freeze / promotion)

```bash
curl -s -X POST localhost:8080/v1/content/corpora/1/freeze -d '{"label":"v1"}'
curl -s -X POST localhost:8080/v1/content/versions/1/tag -d '{"name":"shakespeare/v1"}'
```

## 5. Pin the version in a training run

```bash
curl -s -X POST localhost:8080/v1/training/start \
  -H 'content-type: application/json' \
  -d '{"n_embd":16,"content_version_id":1,"num_steps":200}'
# The run logs corpus_ref=<manifest_digest>, a MetaDataset input, and
# corpus_manifest.json; a VersionRunRef is recorded (lineage + retention protection).
```

## 6. Re-resolve identically after the corpus changes (the core guarantee)

```bash
# Ingest more content into corpus 1 (new session → accept → version 2) ...
# Then re-resolve the ORIGINAL pinned version:
curl -s localhost:8080/v1/content/versions/1 | jq '.data.manifest_digest, .data.entries'
# → identical entry set & digest as step 3, unaffected by later changes (SC-001).
```

## 7. Concurrent isolated ingestion (US2/SC-003)

Open two sessions from two sources, stage different content in each, and confirm neither
sees the other's staged entries; accept both and confirm each lands in the canonical
corpus without disturbing the other. Acceptance is serialized per corpus.

## 8. Revert (safety net, FR-011)

```bash
curl -s -X POST localhost:8080/v1/content/corpora/1/revert -d '{"to_version_id":1}'
```

## Acceptance checks (map to spec SCs)

- [ ] SC-001: pinned version re-resolves to identical content after corpus changes.
- [ ] SC-002: a run-referenced version + its blobs survive cleanup.
- [ ] SC-003: concurrent sessions show zero cross-contamination.
- [ ] SC-004/005: failing content is kept out; passing content auto-folds (no approval).
- [ ] SC-006: composed weighted version reproduces identically.
- [ ] SC-010: full workflow on a clean install with zero configuration / zero awareness
      of any supporting background service.
- [ ] SC-012: per-batch ~5s, pre-acceptance ~30s in the common case.

## Tests

```bash
make test       # unit + integration (TDD; gate/isolation/digest invariants)
make typecheck  # mypy --strict
make lint
```
