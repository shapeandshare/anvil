# Spec Backlog Consolidation — Web UI

**Issue**: [ANV-2](/ANV/issues/ANV-2) — Review and consolidate spec backlog for web UI  
**Date**: 2026-07-06  
**Author**: UX Engineer  

---

## 1. Scope and Methodology

Reviewed all spec files in two locations:
- `specs/` (2 specs — current/recent format with full plan/tasks/data-model)
- `docs/vault/Specs/` (17 specs — historical vault format)

Each spec evaluated for UI relevance, current status, completion level, and design system alignment with `docs/DESIGN.md`, `docs/ux-rules.md`, and `docs/user-requirements.md`.

---

## 2. Spec Inventory — UI-Relevant Items

### 2.1 `specs/` (Current Pipeline)

| Spec | Feature | UI Relevance | Status | Notes |
|------|---------|-------------|--------|-------|
| **064** | Teach Page CTA Remediation (062-teach-page-cta) | **HIGH** — pure frontend | ✅ All tasks complete | Eliminated dead initial state, added empty-state guidance, flow CTAs, progressive disclosure, visual polish. Ready for merge. |
| **065** | Bootstrap Anvil into Paperclip (063-paperclip-bootstrap) | **NONE** — ops script | ✅ US1+US2 complete; ⬜ US3 verification (T020-T029) | Seed script + staffing plan done. Verification tasks remain: run seed, confirm entities in Paperclip UI, test idempotency. Not a UI deliverable. |

### 2.2 `docs/vault/Specs/` (Historical Backlog)

| Spec | Title | UI Relevance | Status | Notes |
|------|-------|-------------|--------|-------|
| **055** | Interactive Teaching Loop | **HIGH** — /v1/teach page, session UI, SSE streaming | Draft | Parent spec that 064 builds on. UI page exists (`teach.html`). Backend implementation via `TrainingRunService` extraction. 064 addresses the frontend CTA gap. |
| **060** | Text Input Theme Consistency | **HIGH** — pure CSS/template | Draft, **not implemented** | The most actionable outstanding UI spec. Orphan input styles across pages (`login-card__input`, bare `<input>` in training params, config modal `class="input"`). 23 behavioral themes need unified input tokens. |
| **041** | HuggingFace Model Browser & Curated Catalog | **HIGH** — new UI page needed | Draft, **not implemented** | Requires search/browse/inspect UI for HF models. Has `domain/ui` tag. New page + model card components. |
| **001** | Non-Educational Help Guide | **MEDIUM** — help page + in-context help links | Draft, **not implemented** | Help content + cross-page help links/CTAs. In-context help (help icons on each workspace page). |
| **057** | Degraded Mode Recovery | **MEDIUM** — UI state for service degradation | Draft | Status indicators, error banners, reconnection UI. Relevant to SSE streaming patterns. |
| **063** | Usable External Models | **LOW** — potentially UI for model import/setup | Draft | Might need import UI wizard. |
| **064** | MLflow Model Catalog | **LOW** — potentially catalog browser UI | Draft | MLflow registry browser. |
| **065** | Adapter Catalog Entries | **LOW** — potentially listing UI | Draft | Adapter management UI. |

### 2.3 Non-UI Vault Specs (for completeness)

| Spec | Title | Reason Excluded |
|------|-------|----------------|
| 026 | Client SDK | No UI — Python library |
| 027 | Deployment Backup Restore | Operational, no UI |
| 028 | Concurrent Isolated Instances | Infrastructure |
| 043 | Subword Tokenizer Abstraction | Backend engine |
| 044 | Local LoRA Fine-Tuning | Training engine |
| 046 | Fine-Tune Compute Routing | Backend service |
| 054 | Fine-Tuned Model Evaluation | Backend service |
| 058 | At-Rest Secret Encryption | Security, no UI |
| 061 | Resilient Startup Recovery | Infrastructure |

---

## 3. UX Debt Assessment

### 3.1 Existing Gaps (Planned)

| Gap | Severity | Spec | Description |
|-----|----------|------|-------------|
| Text input visual inconsistency across pages | **S3** | 060 | Inputs on training, login, config pages use orphan CSS classes. Light mode inputs invisible. No unified `form-input` adoption. |
| No model browser UI | **S2** | 041 | HuggingFace model search/browse requires a new dedicated page. Currently models are selected by drop-down only. |
| No in-context help system | **S2** | 001 | Help content exists but no cross-page help CTAs, no contextual tooltips, no "Related lessons" integration. |
| No degraded-mode UI states | **S2** | 057 | Service degradation has no dedicated UI: no reconnection banners, no offline indicator, no retry affordance beyond generic error. |

### 3.2 Unplanned UX Debt (Not in Any Spec)

| Gap | Severity | Evidence | Description |
|-----|----------|----------|-------------|
| No responsive layout audit | **S2** | DESIGN.md archetypes cover ≤768px/≤480px, but no spec validates every page against these breakpoints | Mobile/tablet layout not systematically verified. |
| No loading/skeleton states | **S2** | Most pages show spinners for content loading, but no skeleton/placeholder patterns exist | Skeleton screens would improve perceived performance. |
| No error boundary UI | **S3** | No spec defines error boundary component or page-level error state | JS errors crash panels silently. UX rules require S3 error handling. |
| No empty-state patterns for data pages | **S3** | Only the teach page (064) has a defined empty state. Other data pages (experiments, models, datasets) have no guidance on first visit | UX rules require S3 empty-state handling. |
| Keyboard navigation incomplete | **S3** | UX rules require S4/S3 keyboard operability, but no spec validates full keyboard flow across every page | Tab order, skip links, and `:focus-visible` not systematically audited. |
| No form validation UX pattern | **S2** | UX rules require inline error rendering (S3), but no spec defines a unified form validation UX | Each form implements validation independently. |

---

## 4. Polish Priorities

Priority-ranked work items for web UI, based on user impact × effort:

### P0 (Critical — Must Fix)

None currently identified. The teach page (064) resolved the most critical dead-state gap.

### P1 (High — Next Sprint)

| # | Item | Spec | Effort | Rationale |
|---|------|------|--------|-----------|
| 1 | **Unify text input styling** | 060 | 1-2 sprints | Most visible polish gap. Fixes inconsistency across all pages. Unlocks theme consistency for 23 themes. 44px touch targets for mobile. |
| 2 | **Define and apply empty-state patterns** | None (gap) | 1 sprint | UX rules require S3 empty-state handling. Every data-viewing page needs a guidance card pattern (following 064's lead). |

### P2 (Medium — Near-term)

| # | Item | Spec | Effort | Rationale |
|---|------|------|--------|-----------|
| 3 | **In-context help system** | 001 | 2 sprints | Help CTAs on each page, tooltip component, "Related lessons" integration |
| 4 | **Error boundary UI component** | None (gap) | 1 sprint | Catch-all error state for panels, graceful degradation, retry affordance |
| 5 | **Degraded-mode UI states** | 057 | 1-2 sprints | Reconnection banners, offline indicators, SSE retry UI |
| 6 | **HuggingFace Model Browser** | 041 | 3-4 sprints | New page + search + model card components. Largest effort. |

### P3 (Low — Future)

| # | Item | Spec | Effort | Rationale |
|---|------|------|--------|-----------|
| 7 | Keyboard navigation audit | None (gap) | 1 sprint | Verify tab order, skip links, focus-visible across all templates |
| 8 | Responsive layout audit | None (gap) | 1 sprint | Validate all pages at ≤768px and ≤480px breakpoints |
| 9 | Skeleton loading patterns | None (gap) | 1 sprint | Replace spinners with skeleton/placeholder screens |
| 10 | Unified form validation UX | None (gap) | 1 sprint | Standard inline error rendering, focus-first-error pattern |
| 11 | Model Catalog / Adapter browser UIs | 064, 065 | 2-3 sprints each | MLflow-based browsing UI, adapter listing |

---

## 5. Design System Gaps

### 5.1 Tokens/Components Missing

| Gap | Impact | Recommendation |
|-----|--------|---------------|
| No unified input component tokens | Inputs don't respond to behavioral themes | Add `--bg-input`, `--border-input`, `--focus-ring-input` tokens (or verify `--surface-2` + `--accent` works across all themes, per spec 060) |
| No empty-state component pattern | Each page implements its own | Create `.empty-state` component class with icon, message, CTA pattern (follow `section-card` from 064) |
| No error boundary component | No graceful failure UI | Create `.error-boundary` component with retry affordance |
| No skeleton/placeholder pattern | Spinners are the only loading indicator | Create `.skeleton` component with shimmer animation |
| No form validation component | Inline error rendering inconsistent | Create `.form-error` component with focus management |

### 5.2 Pattern Inconsistencies

| Issue | Location | Rule |
|-------|----------|------|
| `class="input"` orphan | Config modal | UX rules require consistency (S2) |
| `login-card__input` orphan | Login page | UX rules require consistency (S2) |
| Bare `<input>` in `training.html` param blocks | Training form | UX rules require component classes |
| Compute backend `<select>` with inline styles | Config modal | UX rules prohibit inline styles |
| No `class="form-input"` on `<select>` elements | Various | Selects should share input styling per spec 060 |

### 5.3 Behavioral Theme Gaps

| Theme Impact | Severity | Spec |
|-------------|----------|------|
| Inputs don't adapt to behavioral themes | **S3** — degrades theme consistency | 060 |
| Light mode inputs invisible (`--surface-2` = page bg) | **S3** — usability failure | 060 |
| No spec validates theme appearance across all pages | **S2** — quality gap | None |

---

## 6. Recommendations

### Immediate Actions

1. **Merge 064** (teach page CTA). All tasks complete, UX lint verified. Closes the critical UX dead-state gap.
2. **Start spec 060** (text input theme consistency). Highest-impact remaining UI work. Unifies the most visible inconsistency.
3. **Create new issue** for empty-state component pattern — every data page needs it.

### Next Sprint

4. **Begin spec 001** (help guide) — help system is foundational for usability.
5. **Define error boundary component** — addresses the unplanned S3 gap.

### Within 1 Month

6. **Begin spec 041** (HF model browser) — largest UI feature remaining.
7. **Begin spec 057** (degraded mode) — needed for production reliability UX.

### Ongoing

8. Add **design system tokens** for input components, empty states, and error boundaries to close the gap before new features.
9. Run a **keyboard navigation audit** and **responsive layout audit** across all pages.
10. Create a **UX quality checklist** that each new feature spec must include (empty states, error states, loading states, keyboard operability, responsive behavior, theme consistency).

---

## 7. Spec Quality Observations

- **Specs in `specs/`** are more complete (have plan/tasks/data-model/quickstart/research/checklists)
- **Vault specs** vary in quality: some have full scenarios and requirements (055, 060), others are minimal (001)
- **No cross-referencing** between vault specs and `specs/` pipeline — 064 (teach CTA) is a follow-up to 055 (teaching loop) but they reference each other only implicitly
- **No spec index** exists — this document serves as the first consolidated inventory

### Recommendations for Spec Quality

- Vault specs should link to their `specs/` implementation branch when one exists
- New specs should follow the `specs/` format (spec.md + plan.md + tasks.md + data-model.md + quickstart.md + research.md + checklists/)
- Each new spec should include a UX section covering empty states, error states, loading states, and keyboard operability