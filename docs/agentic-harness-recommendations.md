# anvil — Agentic Harness Cleanup: Remaining Work

**Updated**: 2026-06-21 — tracking what's left after the June 19 recommendations were actioned.

---

## Status Summary

**7 of 9 original findings resolved.** Remaining: 2 original + 2 new findings.

| # | Issue | Severity | Status |
|---|-------|----------|--------|
| 1 | CI quality gates | 🔴 Critical | ✅ Done |
| 2 | `TYPE_CHECKING` contradiction | 🔴 Critical | ✅ Done |
| 3 | Coverage gate fiction | 🔴 Critical | ✅ Done |
| 4 | God Class half-implemented | 🟠 High | ✅ Done |
| 5 | `router.py` monolith | 🟠 High | ✅ Done |
| 6 | Thin onboarding docs | 🟠 High | ✅ Done |
| 7 | ADR number collisions (original 3) | 🟡 Medium | ✅ Done |
| 8 | Vault human entry point | 🟡 Medium | ✅ Done |
| **9** | **Trim AGENTS.md drift** | 🟡 Medium | ❌ |
| **10** | **Clean stale ADR files** | 🟡 Medium | ❌ |
| **11** | **Fix stale doc references** | 🟡 Medium | ❌ |

---

## Remaining Work

### 9. Trim AGENTS.md state-tracking drift

AGENTS.md is 332 lines with `Active Technologies` (lines 262-309) and `Recent Changes` (lines 311-332) — manually-maintained sections that duplicate `CHANGELOG.md` and bloat agent context.

**Action**: Remove both sections from AGENTS.md. The `Recent Changes` content already lives in `CHANGELOG.md` (automated via commitizen). Active Technologies is documented in individual ADRs.

---

### 10. Remove residual ADR collision files

After renumbering (ADR-029), old occupant files were not cleaned up. Two collisions remain on disk:

| Number | Colliding files |
|--------|----------------|
| **023** | `ADR-023-data-page-tabbed-layout.md` + `ADR-023-responsible-data-governance.md` |
| **025** | `ADR-025-numpy-docstring-enforcement.md` + `ADR-025-vault-health-subsumption.md` |

**Action**: Delete the old occupant files (the pre-renumbering originals). Verify `make vault-audit` passes.

---

### 11. Fix stale cross-references in documentation

| File | Line | Stale text | Correct text |
|------|------|-----------|-------------|
| `ARCHITECTURE.md` | 19 | God Class at `anvil/cli.py` | God Class at `anvil/workbench.py` |
| `docs/testing-guide.md` | 220 | "Current coverage: ~41%" | See `fail_under` in `pyproject.toml` (currently 23) |
| `docs/testing-guide.md` | 220 | "TDD mandate targets 100%" | TDD uses ratcheting coverage baseline (ADR-026) |

**Action**: Edit the three stale lines. Low effort, removes agent-confusion vectors.

---

## Appendix: Evidence Locations

- AGENTS.md: `AGENTS.md` (332 lines)
- ADR collisions: `docs/vault/Decisions/ADR-023*`, `docs/vault/Decisions/ADR-025*`
- Stale refs: `ARCHITECTURE.md:19`, `docs/testing-guide.md:220`
- CI workflow: `.github/workflows/ci.yml`
- God Class: `anvil/workbench.py`
- Router: `anvil/api/v1/router.py` (82 lines)
- ADR index: `docs/vault/Decisions/README.md`