---
title: 'ADR-011: Name-Based Idempotency for Demo Data Bootstrap'
type: decision
tags:
- type/decision
- domain/database
- domain/infrastructure
created: '2026-06-14T00:00:00.000Z'
updated: '2026-06-14T00:00:00.000Z'
aliases:
- 'ADR-011: Name-Based Idempotency for Demo Data Bootstrap'
source: agent
---
# ADR-011: Name-Based Idempotency for Demo Data Bootstrap

## Status

Accepted

## Context

The bootstrap-datasets feature imports bundled demo corpora and datasets into the database. The bootstrap command must be safe to run multiple times (idempotent) without creating duplicate entries. The project already has existing entities (`Corpus`, `Dataset`) with unique name constraints, but no mechanism to detect "already imported" demo data.

Three approaches were considered:
1. **Name-based**: Check if an entity with the target name already exists before creating
2. **Content hash-based**: Compute SHA-256 of source files and compare against stored hashes
3. **Path-based**: Track which file paths have been imported via a new registry table

## Decision

Use **name-based** idempotency. The bootstrap command constructs a canonical name for each entity (`"Demo - {size}/{name}"`) and checks if any `Corpus` or `Dataset` with that name exists before creating.

Rationale:
- **No new tables or schema changes** — the existing unique constraint on entity names is sufficient
- **Predictable** — the name is deterministic from the file path, so the same data always maps to the same name
- **Delete-and-reimport** works naturally — deletion frees the name, re-bootstrap recreates
- **Simple to implement** — a single `get_by_name()` method on each repository

## Consequences

**Easier**:
- Bootstrap logic is straightforward — no hash computation, no registry table
- Users can delete demo data and re-import by re-running the command
- Existing DB unique constraints prevent accidental duplicates even without the check

**Harder**:
- Renaming a demo source file creates a new entity rather than updating the old one
- No protection against a user creating a non-demo entity with a conflicting `"Demo - "` name
- If demo content is updated in-place (file changed), re-running bootstrap won't detect the change

## Compliance

- `DemoBootstrapService.bootstrap_all()` must call `get_by_name()` before every `create()`/`create_dataset()`
- Test: `test_bootstrap_all_idempotent` verifies that the second run produces zero new entities
- The `is_demo_entity()` static method provides a consistent check for the naming convention
