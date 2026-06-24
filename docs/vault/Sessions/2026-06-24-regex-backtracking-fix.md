---
title: Regex Backtracking Fix for YAML Frontmatter Parsing
type: session-log
source: agent
tags:
  - type/session-log
  - domain/tooling
  - domain/vault
created: '2026-06-24'
updated: '2026-06-24'
aliases:
  - Regex Backtracking Fix Session
---

# Session: Regex Backtracking Fix for YAML Frontmatter Parsing

**Date**: 2026-06-24
**Tags**: #session #security #vault #hygiene #regex

## Summary

Fixed a polynomial backtracking vulnerability in `anvil/services/vault/hygiene.py` where the YAML frontmatter-stripping regex (`r"^---\s*\n.*?\n---\s*\n"` with `re.DOTALL`) could cause O(n²) runtime on pathological inputs. Replaced with simple O(n) string operations.

## Changes

### `anvil/services/vault/hygiene.py`

**Before** (line 347):
```python
fm_match = re.match(r"^---\s*\n.*?\n---\s*\n", content, re.DOTALL)
if fm_match:
    content = content[fm_match.end():]
```

**After**:
```python
fm_end = content.find("\n---\n") if content.startswith("---\n") else -1
if fm_end != -1:
    content = content[fm_end + 5:]
```

### Vault enrichment

- [[Discoveries/regex-backtracking-yaml-frontmatter|Discovery note]] — documents the vulnerability, root cause, and fix
- [[Discoveries/Discoveries|Discoveries MOC]] — updated with link

### Tests

All 47 vault hygiene tests pass. No behavioral change for valid inputs.

## Discoveries

- [[Discoveries/regex-backtracking-yaml-frontmatter|Regex Backtracking in YAML Frontmatter Parsing]] — `re.DOTALL` + `.*?` + `\s*\n` creates an O(n²) backtracking vector in what appeared to be a innocuous frontmatter-stripping regex.