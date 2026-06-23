---
title: Code
type: moc
tags:
  - type/moc
  - domain/vault
created: 2026-06-21
updated: 2026-06-21
aliases:
  - Code
---

# Code

Code-architecture notes: modules, classes, autoloads, and conventions documented at the implementation level. Where `Systems/` notes describe a bounded subsystem's responsibility, `Code/` notes zoom in on the structure of specific code units — entry points, public APIs, and the decisions baked into a file or package.

Start here when you need to understand how a particular piece of the codebase is shaped, not just what subsystem it belongs to.

## Notes

- (No code notes yet — create with `_meta/templates/code.md`.)

## Conventions

- Carries `type/code` and a `code-refs:` field pointing at the source file(s) it documents.
- Named in Title Case after the code unit (e.g. `Repository Pattern.md`).
- Links up to the `Systems/` note for the subsystem it lives in.

## Related MOCs

- [[Systems/Systems|Systems]] — the subsystems these code units compose
- [[Specs/Specs|Specs]] — specs that drive these implementations
- [[Design/Design|Design]] — conceptual rationale behind the code
