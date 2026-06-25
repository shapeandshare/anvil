---
title: Regex Backtracking Vulnerability in YAML Frontmatter Parsing
type: discovery
source: agent
tags:
  - type/discovery
  - domain/tooling
  - domain/vault
created: '2026-06-24'
updated: '2026-06-24'
aliases:
  - Regex Backtracking Vulnerability in YAML Frontmatter Parsing
  - YAML frontmatter regex backtracking
code-refs:
  - anvil/services/vault/hygiene.py
---

# Regex Backtracking Vulnerability in YAML Frontmatter Parsing

## Problem

The `_find_over_linking` function in `anvil/services/vault/hygiene.py` used a regex with `re.DOTALL` to strip YAML frontmatter from note content before scanning for wikilinks:

```python
fm_match = re.match(r"^---\s*\n.*?\n---\s*\n", content, re.DOTALL)
```

This pattern is vulnerable to **polynomial (O(n²)) backtracking** due to two interacting issues:

1. **`\s*` before `\n` is ambiguous** — `\s` matches `\n`, so when `\s*` greedily consumes multiple newlines, the engine must backtrack one character at a time when `\n` fails to match. This creates O(k) backtracking for k whitespace characters after `---`.

2. **`.*?` with `re.DOTALL` scans all content** — with DOTALL, `.` matches newlines. The lazy `.*?` must incrementally extend through the entire file when no closing `---` exists, testing `\n---\s*\n` at every position.

In the worst case — a vault note with large content and no valid closing frontmatter — the regex engine does O(n²) work: the opening `---\s*\n` consumes initial whitespace with backtracking, then `.*?` extends linearly through the full file, testing `\n---\s*\n` at each position.

## Fix

Replaced the regex with simple O(n) string operations:

```python
fm_end = content.find("\n---\n") if content.startswith("---\n") else -1
if fm_end != -1:
    content = content[fm_end + 5 :]
```

- `content.startswith("---\n")` — constant-time check for frontmatter start
- `content.find("\n---\n")` — single linear scan for the closing delimiter
- No regex engine, no backtracking, no DoS vector

The `\s*` flexibility (allowing trailing whitespace after `---`) was dropped because the project's vault convention uses strict `---\n` (confirmed by the line-by-line parser in `_load_controlled_tags` which checks `line == "---"`).

## Why It Happened

The regex was the most concise way to express "match content between `---` delimiters." It worked correctly for all valid inputs. The vulnerability only manifests on adversarial or pathological inputs — large content with no closing frontmatter — making it easy to miss in normal testing.

## Related
- [[Discoveries/Discoveries|Discoveries]]

- [[Decisions/ADR-015-pluggable-compute-backends|ADR-015]] — none directly; this is a code-level security hardening
- Classic ReDoS (Regular expression Denial of Service) pattern: `\s*\n` ambiguity + `.*?` with DOTALL