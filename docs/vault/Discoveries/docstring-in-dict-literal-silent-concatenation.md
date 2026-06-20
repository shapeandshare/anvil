---
title: Docstring Inside a Dict Literal Silently Concatenates With the First Key
type: discovery
status: draft
source: agent
created: '2026-06-20'
updated: '2026-06-20'
aliases:
  - Docstring Inside a Dict Literal Silently Concatenates With the First Key
related:
  - '[[Sessions/2026-06-20-legacy-backcompat-removal]]'
code-refs:
  - anvil/api/v1/experiments.py
session: 2026-06-20-legacy-backcompat-removal
summary: >-
  A triple-quoted string placed as the first element inside a dict literal is
  not a docstring — Python adjacent-string-literal concatenation fuses it with
  the following key string, deleting that key from the dict. In experiments.py
  this silently dropped the "n_layer" hyperparameter coercer.
tags:
  - type/discovery
  - domain/tracking
  - status/draft
---

A triple-quoted string written as the first element inside a `{...}` dict
literal looks like a docstring but is not one — Python has no concept of a
docstring for a dict, and instead applies implicit adjacent-string-literal
concatenation, fusing the "docstring" with the first key.

This was discovered while updating `_HYPERPARAM_COERCERS` in
`anvil/api/v1/experiments.py`. The constant was written as a dict literal whose
first physical line was a triple-quoted explanatory block, immediately followed
by `"n_layer": int`. Because two adjacent string literals concatenate, the
parser produced a single key equal to the explanatory text glued to `n_layer`
(`"...storage.    n_layer"`) mapped to `int`. The intended `"n_layer"` key never
existed in the dict.

The effect was silent: no syntax error, no runtime error. `_hyperparams_from_mlflow`
simply never coerced `n_layer`, so it was missing from the reconstructed
hyperparameters. A unit test (`test_coerces_known_types`) caught it only because
it asserted `hp["n_layer"] == 4`, which raised `KeyError`. Without that
assertion the bug would have shipped as a quietly dropped field.

The fix is to move the explanatory text *above* the assignment as a real
module-level comment or a preceding string statement, never inside the braces.
The same trap applies to list and set literals: any stray adjacent string
literal will either concatenate with a neighbouring string element or sit as an
unintended element.

This is a latent footgun anywhere a "section header" triple-quoted string is
dropped inside a collection literal for readability. Prefer a `#` comment for
in-literal annotation; reserve triple-quoted strings for genuine module, class,
and function docstrings.

## References

- `anvil/api/v1/experiments.py` — `_HYPERPARAM_COERCERS` constant and
  `_hyperparams_from_mlflow`
