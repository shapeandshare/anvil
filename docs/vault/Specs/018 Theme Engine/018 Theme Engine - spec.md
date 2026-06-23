---
title: 018 Theme Engine - spec
type: spec
tags:
  - type/spec
spec-refs:
  - docs/vault/Specs/018 Theme Engine/
related:
  - '[[018 Theme Engine]]'
created: ~
updated: ~
---
# Feature Specification: Theme Engine (Behavioral Themes)

**Feature Branch**: `018-theme-engine`
**Created**: 2026-06-19
**Status**: Draft
**Input**: User description: "we need to support different themes, they are more than just reskinning. examples included"

## Overview

Today the anvil web UI supports exactly two appearances — **dark** and **light** — selected by a single toggle and applied by swapping color values. The two appearances share identical layout, identical motion, and identical meaning: a theme today changes *what color a thing is*, never *what a thing does*.

This feature introduces **behavioral themes**: a theme is a complete, named presentation system that can change not only palette and typography, but also **motion behavior, layered visual effects, and — critically — the semantic mapping between live application state and what the user sees and hears**.

The two example artifacts provided with this request illustrate the intent:

- **"Old Growth" (CRT/TUI)** — a layered phosphor-green broadcast console where a single application signal (`disturbance`) simultaneously drives scanline flicker, chromatic aberration, text-glyph corruption, and a signal-lock meter. The visual chaos *is* the data.
- **"Forge" (training dashboard)** — the loss curve is rendered as cooling metal (white-hot at high loss, steel-blue as it converges), training throughput drives a glowing "forge core" and spark emission, a checkpoint beat is a cool "quench" flash (rendered in anvil as a periodic training *milestone* — anvil saves no model artifact; see FR-029), and a sample output **resolves out of noise** as loss drops. A divergence (NaN) shatters the sample back into noise and turns the forge red.

In both examples, one or more live values from the running application are mapped — per theme — onto a coordinated set of visual (and potentially audio) responses. **That mapping is the feature.** A theme is therefore a contract: "given these application signals, here is how I express them."

This is explicitly *more than reskinning*. Reskinning (swapping token values) is the floor; behavioral expression is the ceiling.

> **Important context — relationship to prior work**: A previous effort (spec `004-frontend-refactor`) deliberately *removed* an earlier ANSI/CRT/phosphor terminal aesthetic in favor of a clean iOS-modern light/dark system, on the grounds that the retro treatment hurt legibility and accessibility. This feature does **not** undo that decision. The iOS-modern system remains the default and the accessibility baseline. Expressive themes such as "Old Growth" are **opt-in, gated, and degrade gracefully** — they layer expression *on top of* a legible, accessible base, and any user can return to the clean default at any time. See Assumptions and FR-016 through FR-021.

## Clarifications

### Session 2026-06-19

- Q: How faithfully must the "Forge" and "Old Growth" themes reproduce the provided HTML demo files? → A: Behavioral-faithful, cosmetics refine-able — the named effects and signal→expression mappings MUST be reproduced; exact colors, spacing, and timing MAY be refined to fit the app grid and accessibility rules.
- Q: How broadly should an expressive theme apply across anvil's 8 pages? → A: Whole-app identity, signal layer where applicable — the theme's palette/chrome/ambient effects apply to every page consistently; the live signal→expression layer activates only on pages that have live signals (training dashboard, experiments), and static pages get the look without fabricated data effects.
- Q: What is the exact set of themes shipped at launch (v1)? → A: Default + Forge + Old Growth + 1–2 additional new behavioral themes designed fresh for this feature (at least four themes total at launch).
- Q: In "Old Growth", what live training data should drive the abstract "disturbance" signal? → A: Training instability — gradient-norm magnitude and loss volatility/spikes drive disturbance up, a divergence/NaN event pins it to maximum, and a stable converging run keeps it low.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Choose a behavioral theme (Priority: P1)

A user opens the application and wants to change how the entire interface looks and behaves — not just light vs. dark, but selecting from a small gallery of distinct, named themes (e.g. the clean default, a "Forge" theme, an "Old Growth" theme). They pick one, the whole UI transforms, and their choice persists across navigation and reloads.

**Why this priority**: This is the core of the request. Without theme *selection* from more than two options, nothing else in the feature is reachable. It is the minimum viable slice: even if a theme only changed palette + typography + motion (no live-state mapping yet), being able to choose among named themes and have it persist is already a complete, demonstrable unit of value.

**Independent Test**: From any page, open the theme picker, select a non-default theme, navigate to another page and reload — the selected theme is still applied everywhere. Switch back to the default — the clean appearance returns. Fully testable without any live training data.

**Acceptance Scenarios**:

1. **Given** a fresh user with no saved preference, **When** they first load the app, **Then** the default (clean iOS-modern) theme is applied, honoring their operating-system light/dark preference.
2. **Given** a user on any page, **When** they open the theme picker and select a named theme, **Then** the entire interface (all pages, nav, content) re-presents in that theme within a moment, without a full reload.
3. **Given** a user who has selected a theme, **When** they navigate between pages or reload the browser, **Then** the same theme remains applied with no flash of the wrong theme on first paint.
4. **Given** a user who has selected a non-default theme, **When** they choose "default" (or reset), **Then** the clean iOS-modern appearance is restored and persisted.
5. **Given** a theme picker listing the available themes, **When** the user views it, **Then** each theme shows a recognizable name and a preview hint so they can tell themes apart before choosing.

---

### User Story 2 - Themes express live application state (Priority: P1)

A user is watching a live training run with an expressive theme selected. As real training metrics stream in, the theme translates those metrics into its own coordinated visual language — e.g. under "Forge", a falling loss makes the sample text resolve from noise into readable words and shifts the loss curve from white-hot toward steel-blue; under "Old Growth", a rising disturbance signal increases scanline flicker, text corruption, and lowers the signal-lock meter.

**Why this priority**: This is what makes themes "more than reskinning" and is the explicit, distinguishing ask. Both provided examples are fundamentally about mapping live signals to expression. A behavioral theme that ignores application state would be indistinguishable from a reskin.

**Independent Test**: With an expressive theme active, drive the relevant application signal across its range (via a real or simulated live run) and observe that the theme's visual responses move correspondingly and consistently — high-signal vs. low-signal states are visibly, predictably different. Testable by feeding a known sequence of signal values and verifying the expressed output tracks them.

**Acceptance Scenarios**:

1. **Given** an expressive theme is active and a live signal (e.g. training loss, throughput, or a disturbance value) is available, **When** the signal value changes, **Then** the theme's mapped visual responses update to reflect the new value in a coordinated way (multiple responses move together from the single signal).
2. **Given** an expressive theme mapping "convergence/clarity", **When** loss decreases over the course of a run, **Then** the sample/output rendering becomes progressively clearer (less noise/corruption) and the curve's color/temperature shifts accordingly.
3. **Given** an expressive theme, **When** a discrete training event occurs (e.g. a periodic training milestone, or a divergence/NaN), **Then** the theme produces its corresponding distinct response (e.g. a brief "quench"/flash on a milestone; an alarm/degraded state on divergence).
4. **Given** no live run is active, **When** an expressive theme is selected, **Then** it presents a coherent idle/at-rest state (no errors, no frozen or nonsensical readouts) rather than depending on streaming data to look correct.
5. **Given** the same live signal value, **When** two different expressive themes are each given that value, **Then** each expresses it in its own distinct visual language (the mapping is theme-specific, not global).

---

### User Story 3 - Expressive themes never block the work (accessibility & opt-out) (Priority: P2)

A user with motion sensitivity, a low-power device, or a need for maximum legibility wants to use the tool without intense effects. They expect that any theme remains usable — text stays readable, controls stay operable — and that the system automatically tones down or disables heavy effects when the user or device asks for it, without forcing them off their chosen theme.

**Why this priority**: The prior refactor removed an expressive aesthetic specifically for accessibility/legibility reasons. Re-introducing expressive themes is only acceptable if it cannot regress that baseline. This story protects the decision made in `004-frontend-refactor` and is required for the feature to be shippable, but it depends on Stories 1–2 existing first.

**Independent Test**: Enable a reduced-motion / reduced-effects preference (OS-level or in-app), select the most intense expressive theme, and confirm that animations and disruptive effects are suppressed or muted while content remains fully legible and all controls remain operable. Toggle it back and confirm full expression returns.

**Acceptance Scenarios**:

1. **Given** a user (or device) signals a preference for reduced motion, **When** any theme is active, **Then** continuous/looping animations and disruptive transitions are disabled or substantially reduced while the theme's static identity (palette, layout, typography) is preserved.
2. **Given** an expressive theme that degrades legibility through effects (e.g. text corruption, heavy overlays), **When** reduced-effects is requested, **Then** those legibility-degrading effects are suppressed so all primary data and controls are clearly readable.
3. **Given** any active theme, **When** a user wants out, **Then** they can return to the clean default theme in one obvious action from any page.
4. **Given** any theme and mode, **When** text and interactive controls are presented, **Then** they meet the project's established contrast and legibility standards for primary content.
5. **Given** a theme that supports an optional audio dimension (if any), **When** the user has not opted in to sound, **Then** no audio plays by default.

---

### User Story 4 - Light/dark continues to work within themes (Priority: P3)

A user who likes the default experience still expects the existing light/dark behavior. Choosing light vs. dark should continue to work, and themes that have both a light and dark variant should respect that choice; themes that are inherently one or the other should behave sensibly.

**Why this priority**: Preserves existing behavior and user expectations established in `004`. It is additive and lower-risk, so it follows the core theme-selection and expression work.

**Independent Test**: With the default theme, toggle light/dark and confirm both still work and persist. With a theme that defines only a single inherent mode, confirm the light/dark control behaves predictably (either follows the theme or is clearly inapplicable) rather than producing a broken appearance.

**Acceptance Scenarios**:

1. **Given** the default theme, **When** the user toggles light/dark, **Then** the behavior is identical to today (persisted, OS-default-aware, no flash).
2. **Given** a theme that defines both light and dark variants, **When** the user toggles light/dark, **Then** the theme switches to its corresponding variant.
3. **Given** a theme that is inherently single-mode (e.g. an always-dark CRT theme), **When** the user views the light/dark control, **Then** the control reflects that the theme is single-mode in an understandable way and does not render a broken state.

---

### Edge Cases

- **Unknown / removed theme in saved preference**: A persisted theme identifier no longer exists (renamed/removed). The system MUST fall back to the default theme without error and update the stored preference.
- **Theme selected mid-run**: The user switches themes while a live run is streaming. The new theme MUST pick up the current signal values and begin expressing them from the present state, without dropping the live connection or requiring a reload.
- **Signal out of expected range / missing**: A live signal is absent, null, NaN, or outside the modeled range (e.g. loss spikes, NaN divergence). Each theme MUST present a defined response (clamp, idle, or an explicit "diverged/error" expression) rather than freezing, throwing, or rendering nonsense.
- **First paint**: On reload with a non-default theme saved, there MUST be no visible flash of the default or wrong theme before the saved theme applies.
- **Reduced-motion changes at runtime**: The user toggles their motion preference while an expressive theme is animating. Effects MUST adjust without requiring a reload.
- **Very low-end / background tab**: When the tab is hidden, continuous effects MUST pause/throttle and resume when visible (FR-021); under heavy device load they SHOULD additionally reduce intensity to preserve interactivity (FR-031).
- **Theme without an expressive layer**: A purely cosmetic theme (palette + type only) MUST be valid — expression is optional per theme, not mandatory.
- **Theme changed in another browser tab/window**: When the persisted preference changes in one tab, other open tabs SHOULD reflect the new theme on next focus/navigation and MUST NOT break or desync into an inconsistent state.
- **Divergence on a non-default theme vs. default**: Divergence stops the run and is shown as failed/diverged in every theme (FR-030); expressive themes additionally render their degraded state, but the run-status outcome is identical regardless of theme.

## Requirements *(mandatory)*

### Functional Requirements

**Theme selection & persistence**

- **FR-001**: The system MUST allow users to choose from a set of named themes (more than the current two appearances), presented in a discoverable picker that shows each theme's name and a preview hint.
- **FR-002**: The system MUST apply a selected theme's visual identity (palette, chrome, ambient effects) across the entire interface — all pages, navigation, and content — consistently. The theme's live signal→expression layer (FR-009–FR-012) MUST activate only where a live training stream is present (e.g. the training dashboard, or any run view showing an active run); on pages without a live stream, the theme presents its at-rest visual identity without fabricated data effects.
- **FR-003**: The system MUST apply a theme change without requiring a full-page reload.
- **FR-004**: The system MUST persist the user's selected theme across navigation and browser reloads.
- **FR-005**: On first visit with no saved preference, the system MUST apply the default theme and honor the operating-system light/dark preference.
- **FR-006**: The system MUST apply the saved theme before first visible paint, with no flash of an unselected theme.
- **FR-007**: Users MUST be able to return to the default theme in one obvious action from any page.

**Behavioral / expressive themes (the core differentiator)**

- **FR-008**: A theme MUST be able to define, beyond palette, at least: typography treatment, motion behavior, and layered visual effects — such that two themes can differ in behavior and feel, not only color.
- **FR-009**: A theme MUST be able to declare a mapping from one or more live application signals (e.g. training loss, token throughput, gradient norm, a periodic training-milestone event, a divergence event, an abstract "disturbance"/intensity value) to its own coordinated set of visual responses.
- **FR-010**: When a mapped live signal changes, the system MUST update the active theme's mapped responses to reflect the new value, such that multiple responses can be driven coherently from a single signal.
- **FR-011**: Each theme's signal→expression mapping MUST be theme-specific: the same signal value MAY be expressed differently by different themes.
- **FR-012**: A theme MUST be able to express discrete application events (e.g. a periodic training milestone, run completion, divergence/NaN, error) as distinct responses separate from continuous-signal expression.
- **FR-013**: Expressive themes MUST present a coherent idle/at-rest state when no live signal is available, without errors or frozen/nonsensical readouts.
- **FR-014**: The system MUST support purely cosmetic themes (palette/type only, no live expression) as valid — the expressive layer is optional per theme.
- **FR-015**: The set of themes MUST be extensible — adding a new theme MUST NOT require redesigning the theming system, and each theme MUST be self-contained (its identity, palette, behavior, and signal mapping defined together).

**Accessibility, safety, and opt-out (non-negotiable)**

- **FR-016**: All themes, in all modes, MUST keep primary data and interactive controls legible and operable, meeting the project's established contrast/legibility standards for primary content.
- **FR-017**: When a reduced-motion preference is signaled (by OS or in-app), the system MUST disable or substantially reduce continuous/looping animations and disruptive transitions for any active theme, while preserving the theme's static identity.
- **FR-018**: When a reduced-effects / maximum-legibility preference is active, the system MUST suppress legibility-degrading effects (e.g. text corruption, heavy overlays) so all primary content and controls remain clearly readable, regardless of theme.
- **FR-019**: The default theme MUST remain the clean, accessible iOS-modern light/dark system established in prior work; expressive themes MUST be opt-in and MUST NOT alter the default experience for users who do not select them.
- **FR-020**: If a theme offers an optional audio dimension, audio MUST be off by default and only play after explicit user opt-in.
- **FR-021**: The system MUST throttle or pause continuous effects when the interface is not visible (e.g. hidden/background tab) to avoid unnecessary resource use, resuming when visible again.

**Light/dark continuity**

- **FR-022**: The existing light/dark toggle behavior MUST be preserved for the default theme (persisted, OS-default-aware, no flash).
- **FR-023**: Themes that define both light and dark variants MUST respect the user's light/dark choice; single-mode themes MUST behave predictably and communicate their single-mode nature without rendering a broken state.

**Resilience**

- **FR-024**: If a saved theme preference references a theme that no longer exists, the system MUST fall back to the default theme without error and reconcile the stored preference.
- **FR-025**: When a mapped signal is missing, null, NaN, or out of the modeled range, the active theme MUST present a defined response (clamp, idle, or explicit error/diverged expression) rather than failing.
- **FR-026**: Switching themes during a live run MUST NOT drop the live data connection; the newly selected theme MUST begin expressing from the current signal values.

**Reference theme fidelity**

- **FR-027**: For themes derived from the provided demo files ("Forge", "Old Growth"), the system MUST reproduce each demo's named effects and signal→expression mappings — for "Forge": loss rendered as cooling-metal color/temperature, throughput-driven forge core and sparks, sample output resolving from noise as loss falls, a "quench" flash on a periodic training milestone (anvil performs no model-checkpoint save; the beat is a neutral milestone marker — see FR-029), and a divergence/NaN state that shatters the sample to noise and shifts to an alarm color; for "Old Growth": a single disturbance signal coherently driving scanline flicker, chromatic aberration, text-glyph corruption, and an inverse signal-lock meter, where **disturbance is derived from training instability** — gradient-norm magnitude and loss volatility/spikes raise it, a divergence/NaN event pins it to maximum, and a stable converging run keeps it near zero (idle/calm when no run is active). Exact colors, spacing, glyph sets, and effect timing MAY be refined to fit the app grid and accessibility rules; the behavioral mappings MUST NOT be omitted.
- **FR-028**: The launch (v1) theme set MUST include at least four themes: the clean iOS-modern default, "Forge", "Old Growth", and at least one additional new behavioral theme designed for this feature. Each behavioral theme MUST satisfy FR-008 (differs in behavior/feel, not only color) and, where it consumes live signals, FR-009–FR-013.

**Neutral signal instrumentation (theme-independent backend behavior)**

- **FR-029**: To feed expressive themes, this feature adds neutral, theme-independent signals to the existing live training stream: per-step **gradient norm** (where the training backend can provide it; absent values are permitted), **token throughput**, a **periodic training-milestone marker**, and **divergence (non-finite loss) detection**. These signals MUST be emitted identically regardless of the active theme (including the default), MUST NOT carry any theme-specific value, and MUST NOT alter training results. The milestone marker is a periodic progress beat only — it does **not** save a model checkpoint or write any artifact.
- **FR-030**: On divergence (loss becomes NaN/inf), the system MUST stop the affected training run and mark its persisted status as terminally failed/diverged, rather than continuing to train on non-finite loss. This behavior is independent of the active theme; the divergence signal additionally lets themes express a distinct degraded state (FR-012).
- **FR-031**: Expressive effects MUST NOT impair the usability of the underlying tool. Primary controls MUST remain responsive while effects animate, and the system MUST reduce effect intensity before allowing any perceptible loss of interactivity on baseline supported hardware (this complements the visibility throttling in FR-021).

### Key Entities *(include if feature involves data)*

- **Theme**: A named, self-contained presentation system. Attributes: identifier, display name, preview hint, supported mode(s) (light, dark, or single-mode), static identity (palette, typography, layout treatment, motion behavior, layered effects), and an optional expressive layer. Themes are extensible and independent of one another.
- **Signal Mapping (per theme)**: The declared relationship between live application signals and a theme's coordinated responses. Attributes: which signals it consumes (continuous values and/or discrete events), the modeled range/expected domain of each, and the resulting responses (visual and optionally audio). One signal may drive several responses; the mapping is owned by the theme.
- **Application Signal**: A live value or event sourced from the running application that a theme may consume. v1 signals: training loss, step, timing rate, token throughput, gradient norm, a periodic training-milestone event, a divergence/NaN event, and run completion. (Validation loss is NOT computed by the engines today and is out of scope for v1 — a possible future signal.) Signals exist independent of any theme; themes choose which to consume; the "disturbance"/intensity value is theme-derived, not a backend signal.
- **Theme Preference**: The user's persisted choice. Attributes: selected theme identifier and light/dark choice; reconciled to the default if the referenced theme is unavailable.
- **Effect / Accessibility State**: The current effective level of expression. Attributes: reduced-motion active (OS or in-app), reduced-effects/legibility active, audio opt-in state, and visibility/throttle state. Governs how strongly the active theme expresses itself.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user can discover, select, and apply any available theme from any page, and the choice persists across reloads, in under 10 seconds and with no full-page reload required for the switch.
- **SC-002**: The application offers at least four distinguishable themes at launch — the clean default, "Forge", "Old Growth", and at least one additional new behavioral theme — and an evaluator presented with the same live signal in each can correctly tell the themes apart 100% of the time.
- **SC-003**: For each expressive theme, driving its primary live signal across its full range produces a correspondingly different presentation at the low, middle, and high ends, verifiable in 100% of trials.
- **SC-004**: For each expressive theme, every defined discrete event (milestone, completion, divergence/error) produces its distinct, observable response in 100% of trials.
- **SC-005**: With reduced-motion enabled, no theme exhibits continuous looping animation or disruptive transitions, while all primary content and controls remain present and legible — verified across every theme.
- **SC-006**: With reduced-effects/maximum-legibility enabled, all primary data and controls meet the project's contrast/legibility standard in every theme and mode, with zero unreadable elements.
- **SC-007**: Users who never open the theme picker experience the default theme's **visual appearance and interactions** exactly as before this feature. (The only intentional behavior change for all users — including default-theme users — is the neutral divergence-halt of FR-030; this is independent of theming and is covered by SC-012.)
- **SC-008**: No saved-preference, missing-signal, out-of-range, or theme-removed condition produces a user-visible error, broken layout, or frozen UI in any tested scenario.
- **SC-009**: A new theme can be added to the gallery without modifying the shared theming system, demonstrated by adding one additional theme end-to-end.
- **SC-010**: On first paint after reload with a non-default theme saved, there is no observable flash of an unselected theme.
- **SC-011**: With the most effects-heavy theme active on the live training dashboard, users perceive no input lag or stutter when operating controls on baseline supported hardware, and continuous effects stop promptly when the tab is hidden.
- **SC-012**: A run whose loss becomes non-finite (NaN/inf) is stopped and shown as diverged/failed (not left appearing to "train") within one update cycle, regardless of the active theme.

## Assumptions

- **Default preserved**: The clean iOS-modern light/dark design from `004-frontend-refactor` remains the default and the accessibility baseline. This feature is additive and opt-in; it does not reverse the removal of the old mandatory ANSI/CRT terminal chrome — instead it offers such aesthetics as *opt-in, gated, gracefully-degrading* themes.
- **Two provided HTML files are behavioral references**: `oldgrowth_tui_crt_demo.html` (CRT/TUI "Old Growth") and `anvil_dashboard_demo.html` ("Forge" dashboard) define at least two of the launch themes. Per the 2026-06-19 clarification, their **named effects and signal→expression mappings are binding** (must be reproduced), while their exact colors, spacing, glyph sets, and effect timing **may be refined** to fit the app's grid and accessibility constraints. See FR-027.
- **Signals are partly existing, partly added**: The live application already streams `loss`, `step`, and a per-step timing rate. Implementation review found that `grad_norm`, token throughput (`tokens_per_sec`), divergence/NaN detection, and a periodic "quench"-beat marker do **not** exist today and are added by this feature as a small, neutral widening of the per-step signal carrier (see plan.md / research.md R1–R5). `grad_norm` is exact on the GPU/torch backend and may be absent on the pure-stdlib backend (themes degrade gracefully). Real periodic model checkpointing is out of scope — the "quench" beat is a neutral `milestone` marker that writes no artifact. Divergence detection additionally **stops the diverged run** (FR-030) — a deliberate, theme-independent behavior change introduced by this feature. The "disturbance"/intensity value is theme-specific and is derived client-side from the neutral signals (R6), never emitted by the backend.
- **Client-driven selection & persistence**: Theme selection and light/dark choice are user-local preferences persisted on the client by default. Server-side per-user persistence is out of scope for the first version unless explicitly added later.
- **No new real-time transport required**: Live state already reaches the UI via the existing streaming mechanism; themes attach to that existing stream rather than introducing a new channel.
- **Scope boundary**: User-authored custom themes, a live color-picker/theme editor, and per-component theme overrides are out of scope for the first version. The first version delivers a curated, extensible gallery of built-in themes.
- **Audio is optional and off by default**: If any theme includes sound, it is strictly opt-in.
- **Mobile/responsive parity**: Themes are expected to work across the device sizes the app already supports; expressive effects may scale down on small or low-power devices.
