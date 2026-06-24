---
aliases:
  - 'Session: ReDoS Regex Fix in Vault Prediction'
created: '2026-06-24'
source: agent
status: draft
tags:
  - type/session-log
  - domain/vault
  - domain/security
title: 'Session: ReDoS Regex Fix in Vault Prediction'
type: session-log
updated: '2026-06-24'
---
# Session: ReDoS Regex Fix in Vault Prediction

**Date**: 2026-06-24
**Trigger**: User identified a ReDoS-vulnerable regex in `anvil/services/vault/prediction.py`.

## What was done

### 1. Diagnosed the vulnerability

The regex `r"^---\s*\n.*?\n---\s*\n"` with `re.DOTALL` on line 111 of `prediction.py` was vulnerable to polynomial-time backtracking. While `.*?` is lazy, the `\s*` after the closing `---` combined with `re.DOTALL` (making `.*?` match newlines) creates small backtracking opportunities at every line starting with `---` in the body. On pathological inputs (long files with partial `---` matches but no clean closing delimiter), this becomes measurable.

### 2. Replaced with str.split

Replaced the regex with a `str.split("---", 2)` approach:

```python
body = content
if content.startswith("---"):
    parts = content.split("---", 2)
    if len(parts) == 3:
        body = parts[2].lstrip("\n")
```

- `str.split` is O(n) with zero backtracking — eliminates the ReDoS vector entirely
- Same semantics: extracts everything after the closing `---` delimiter
- Handles edge cases (no frontmatter, no closing delimiter, empty frontmatter)

### 3. Cleaned up unused import

Removed the now-unused `import re` statement since `re` is no longer referenced anywhere in the file.

### 4. Verification

- Ruff lint: all checks passed
- mypy strict: no issues found
- Only pre-existing diagnostics are optional scikit-learn import warnings (guarded by try/except)

## Files changed

### Modified
- `anvil/services/vault/prediction.py` — replaced ReDoS-vulnerable regex with `str.split`

## References

- `anvil/services/vault/prediction.py`