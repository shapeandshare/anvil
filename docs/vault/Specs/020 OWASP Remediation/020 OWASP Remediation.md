---
title: 020 OWASP Remediation
type: spec
tags:
  - type/spec
  - domain/vault
spec-refs:
  - docs/vault/Specs/020 OWASP Remediation/
status: draft
created: '2026-06-21'
updated: '2026-06-22'
aliases:
  - 020 OWASP Remediation
---

# 020 OWASP Remediation

## Summary

- Q: Should authentication protect only API routes (`/v1/...`), or also the web UI page routes (`/`, `/v1/datasets-page`, etc.)? → A: Protect both API and page routes — all HTTP routes require authentication. Web UI gets a login page redirect; API routes return 401/403.

## Artifacts

- [[020 OWASP Remediation - data-model|data-model]]
- [[020 OWASP Remediation - plan|plan]]
- [[020 OWASP Remediation - quickstart|quickstart]]
- [[020 OWASP Remediation - research|research]]
- [[020 OWASP Remediation - spec|spec]]
- [[020 OWASP Remediation - tasks|tasks]]

## References

- [[Specs/Specs|Specs]]
