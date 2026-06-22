# Specification Quality Checklist: OWASP Top 10 Security Remediation

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-06-21
**Feature**: [spec.md](../spec.md)

## Content Quality

- [x] No implementation details (languages, frameworks, APIs)
- [x] Focused on user value and business needs
- [x] Written for non-technical stakeholders
- [x] All mandatory sections completed

## Requirement Completeness

- [x] No [NEEDS CLARIFICATION] markers remain
- [x] Requirements are testable and unambiguous
- [x] Success criteria are measurable
- [x] Success criteria are technology-agnostic (no implementation details)
- [x] All acceptance scenarios are defined
- [x] Edge cases are identified
- [x] Scope is clearly bounded
- [x] Dependencies and assumptions identified

## Feature Readiness

- [x] All functional requirements have clear acceptance criteria
- [x] User scenarios cover primary flows
- [x] Feature meets measurable outcomes defined in Success Criteria
- [x] No implementation details leak into specification

## Validation Log

| Iteration | Date | Result | Issues Found |
|-----------|------|--------|-------------|
| 1 | 2026-06-21 | **ISSUES FOUND** | Gap: A09-003 and A09-004 (print() instead of logging) not addressed by any FR. Old FR-019 (Docker pinning) was accidentally replaced by new logging FR. |
| 2 | 2026-06-21 | **PASS** | Fixed: Added FR-019 (print()→logging), restored Docker pinning as FR-020, renumbered through FR-024, added SC-009. All 35 findings now addressed. |
| 3 | 2026-06-21 | **REVISED (adversarial review)** | Independent security review (Oracle attempt + artistry pass + codebase fact-check) found 5 CRITICAL + 7 HIGH issues. Added FR-025..FR-031; revised FR-004 (MLflow proxy), FR-008 (ReDoS stdlib timeout), FR-021 (health split); spun out C-3 to spec 018 + ADR-036; authored ADR-035 (MLflow proxy); updated SaaS spec 014. See review summary in `plan.md` §Post-Review Revisions. |
| 4 | 2026-06-21 | **PASS (cross-artifact analyze)** | `/speckit.analyze` found 1 CRITICAL (TDD/Article-IV conflict), 2 HIGH (FR-006 uncovered; T015 `/login`-exempt contradiction), 4 MED/LOW. All fixed: added TDD `t`-suffix test tasks + reconciled the "no test-before" note + plan Article IV; added T016b (FR-006 body-size limit); fixed T015 (`/login` not exempt); de-`[P]`'d T003; corrected Phase-3 MLflow test wording; T018 now covers release.yml; refreshed parallel notes. FR coverage 31/31 = 100%. |
| 5 | 2026-06-21 | **PASS (remediation expansion)** | Follow-up remediation added the FULL set of `t`-suffix test tasks: T001t, T002t, T004t, T005t, T009t **+ T010t, T015t, T016t, T017t, T021t, T023t** (10 total) so every NEW behavior is test-first per Article IV. Added T029b (FR-018 startup-failure logging), T034b (Playwright login/SSE browser e2e) and T034c (Docker system test with auth). Widened FR-031/T004b to all three conftest fixtures. |
| 6 | 2026-06-21 | **PASS (final codebase fact-check after `main` merge)** | Two parallel `explore` agents verified every file:line claim against current HEAD. Fixed drift: `body: dict` is 18 across **8** files — `training.py` uses `config: dict` (T005), and `learning.py`/`content.py`/`datasets.py` were MISSED (added T008b); inference.py is **7** not 8. `str(exc)` is **~34 across 8 files** not "41 across 9" — `training.py`=2 (not 6), `experiments.py`=1 f-string (not 2), `eval_datasets.py`=**0** (not 3); T014 now carries the authoritative line list. Line drift corrected: torch L54 (not 55), SonarCloud L128 (not 125), `/v1/health` L77-115 (not 70-88), TOCTOU `acquire_lock` L1071-1117 (not 1085-1094), regex `re.compile` L294-295. Clarified `get_mlflow_browser_uri` returns a dynamic host:port (not hardcoded :5001). Confirmed real bugs intact: missing `UNIQUE(scope)` on `content_locks`, missing `html=False`, unpinned Docker FROM, `--host 0.0.0.0`/`--allowed-hosts "*"`. |

## Review Findings → Resolution Map

| Finding | Severity | Resolution |
|---------|----------|------------|
| C-1 ReDoS `re.compile(timeout=)` impossible | CRITICAL | FR-008 rewritten to stdlib execution-timeout; `contracts/security-config.md` §4; T017 |
| C-2 SSE breaks under header-only auth | CRITICAL | FR-025 cookie fallback; `contracts/auth-middleware.md`; future-remediation markers |
| C-3 `/v1/` API/page collision + needless versioning | CRITICAL | Spun out → spec `018-header-api-versioning` + ADR-036 (greenfield, no back-compat) |
| C-4 API key written to logs | CRITICAL | FR-026; data-model; quickstart; T001/T004 |
| C-5 MLflow restriction breaking + insufficient | CRITICAL | FR-004 → reverse proxy; ADR-035; SaaS spec 014 unified; T009 |
| H-1 No CSRF | HIGH | FR-027; SameSite=Strict; CSRF token in auth contract |
| H-2 `/login` unthrottled | HIGH | FR-028; login removed from rate-limit exemptions |
| H-3/migration test+healthcheck break | HIGH | FR-031; T004b |
| H-4 version disclosure on exempt route | HIGH | FR-021 rewritten; `/v1/health/detailed` split; T012 |
| H-5 only 4/97 except:pass fixed | HIGH | FR-030; T029 full triage |
| H-7 CORS preflight blocked / mw order | HIGH | FR-029; middleware order documented |

## Notes

- Original 35 findings: FR-001..FR-024 (2 wontfix out of scope). Review-derived: FR-025..FR-031.
- C-3 (URL de-versioning) is intentionally a SEPARATE feature (spec 018 + ADR-036); spec 017's auth contract works before and after it via an explicit page-route registry.
- New ADRs: **ADR-035** (MLflow reverse proxy), **ADR-036** (header-based versioning). SaaS spec 014 FR-057/FR-057c cross-referenced for the unified proxy.
- Status: revised post-review AND post-analyze. FR coverage 31/31 = 100%; TDD test tasks added per Article IV; no remaining CRITICAL/HIGH analyze findings. Ready for `/speckit.implement`.
