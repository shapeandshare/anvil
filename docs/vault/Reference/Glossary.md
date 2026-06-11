---
title: Glossary
type: reference
tags: [type/reference, domain/governance]
created: 2026-06-10
updated: 2026-06-10
---

# Glossary

| Term | Definition |
|------|------------|
| **microgpt** | The core GPT training engine — ~200 lines of pure Python, zero dependencies |
| **God Class** | `MicroGPTWorkbench` — single entry point exposing all service methods to routes/CLI/tests |
| **FileStore** | Pluggable async file storage abstraction (local filesystem or S3) |
| **Repository** | Data access class encapsulating all DB operations for a single entity |
| **SSE** | Server-Sent Events — unidirectional HTTP streaming for real-time updates |
| **UoW** | Unit of Work — transaction boundary spanning multiple repository operations |
| **ADR** | Architecture Decision Record — documents significant architecture decisions |
| **Vault** | Obsidian-compatible documentation directory at `docs/vault/` |
| **Constitution** | Project governance document (`CONSTITUTION.md`) defining non-negotiable principles |
