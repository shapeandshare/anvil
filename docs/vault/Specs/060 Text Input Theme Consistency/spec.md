# Feature Specification: Text Input Theme Consistency

**Feature Branch**: `060-text-input-theme-consistency`  
**Created**: 2026-06-29  
**Status**: Draft  
**Input**: User description: "text edit box theme consistency"

## Clarifications

### Session 2026-06-29

- Q: Are `<select>` dropdown elements in scope? → A: Yes, selects are in scope alongside text inputs.
- Q: Should disabled and read-only input states be styled? → A: Yes — disabled = reduced opacity (0.4) + no focus ring; readonly = shifted background tone with normal focus behavior.
- Q: Focus ring pattern — `:focus` or `:focus-visible`? → A: `:focus-visible` — focus ring appears only on keyboard navigation, not mouse clicks.
- Q: Should the login page inputs be included? → A: Yes — login inputs must be unified into the same component class.

## User Scenarios & Testing

### User Story 1 — Consistent Input Appearance in Dark and Light Mode (Priority: P1)

A user navigates between different pages of the application (training, datasets, playground, config) and enters text or numbers into form fields. Every text input they encounter — search bars, dataset name fields, hyperparameter boxes, prompt entry fields — should have a consistent visual treatment: the same background, border, corner radius, padding, focus indicator, and placeholder style, regardless of which page they are on.

**Why this priority**: Inconsistency in basic form controls is the most visible UI quality issue. Users subconsciously judge polish by form element consistency. Fixing the foundation (all inputs look the same) is prerequisite to theming.

**Independent Test**: A reviewer can open any two pages with text inputs and visually compare their styling side by side — they should be indistinguishable in structure.

**Acceptance Scenarios**:

1. **Given** a text input on any application page, **When** the page loads, **Then** the input has a visually distinct boundary (border or colored background contrast) that clearly marks it as an editable text field.
2. **Given** text inputs on two different pages (e.g., training form and dataset form), **When** viewed side by side, **Then** they share the same background color, border treatment, border radius, padding, font size, and placeholder color.
3. **Given** a text input in light mode, **When** toggling to dark mode, **Then** the input's background, text, border, and placeholder remain individually discernible (minimum 3:1 contrast against the containing surface).

---

### User Story 2 — Themed Inputs Adapt to Behavioral Themes (Priority: P1)

A user activates any of the 23 behavioral themes (Forge, Aurora, Tide, Bloom, Glacier, Tectonic, Storm Front, etc.) via the theme picker. Text inputs should visually adapt to the chosen theme — their background, border, focus ring, and placeholder colors should shift with the theme's custom color tokens, just as panels, buttons, and other components do. In themes with extreme color shifts, inputs must remain usable (legible text, discernible boundaries).

**Why this priority**: Theme consistency is the core ask. Inputs are the last major component class that doesn't respond to theme changes. Users switching themes will notice inputs that "stay the same" while everything else transforms.

**Independent Test**: Activate any behavioral theme, navigate to a page with text inputs, and visually confirm the inputs adopt the theme's color palette. Repeat with 3 contrasting themes (e.g., a light theme, a dark theme, a high-saturation theme).

**Acceptance Scenarios**:

1. **Given** a non-default behavioral theme is active, **When** viewing a text input, **Then** the input's background and border colors derive from the theme's design tokens, not from the base token set.
2. **Given** a theme with reduced legibility (e.g., high contrast, chromatic effects), **When** the user has "Reduce effects" enabled in the theme picker, **Then** inputs revert to a high-legibility variant (solid background, clear border, no decorative effects).
3. **Given** a theme is active, **When** the input receives focus, **Then** the focus indicator (e.g., ring or border highlight) uses the theme's accent color consistently.

---

### User Story 3 — Touch-Friendly Input Targets on Mobile (Priority: P2)

A user on a phone or tablet taps a text input to begin entering data. The input must meet minimum touch-target sizing (44px height) per iOS HIG, making it comfortable to tap without accidentally hitting nearby elements. This applies to all text and number input types across all pages.

**Why this priority**: The app targets an iOS-native feel. Small touch targets erode the native-feeling illusion and frustrate mobile users. However, touch-friendly sizing can be addressed after visual consistency is established.

**Independent Test**: On a phone-width viewport (≤480px), measure the height of each text input type — all must meet or exceed 44px.

**Acceptance Scenarios**:

1. **Given** any text or number input on a mobile viewport, **When** measured, **Then** its total height (padding + line-height + border) is at least 44px.
2. **Given** a tightly packed form, **When** inputs are adjacent, **Then** there is at least 8px vertical gap between touch targets.

---

### Edge Cases

- **Login page orphan**: The login page uses `login-card__input` — its own class — which is a distinct styling path. Must be migrated to the unified input system.
- **Training hyperparameter bare inputs** (training.html): 7 `<input type="number">` elements with zero CSS class — they rely entirely on `.param-block input` rules which use a different background (`--surface` vs `--surface-2`) than the main `.form-input` class. These must be brought into the unified input system.
- **Light mode invisibility**: `--surface-2` in light mode matches the page background, making borderless inputs invisible on the page. A visible border is essential for light mode usability.
- **Zero `<textarea>` elements exist in the app**: If multi-line text editing is ever introduced, it must follow the same visual conventions.
- **Inline style hacks**: Many inputs use inline `style` attributes for width, flex, and layout — these should not override the base input visual style (background, border, radius, padding).
- **Disabled inputs**: Server-rendered forms or loading states may disable inputs — they must be visually distinct (lower opacity, no interaction cues).
- **Read-only inputs**: Fields like auto-filled config values or system-locked settings may be read-only — they need a non-editable visual cue while remaining fully legible.

## Requirements

### Functional Requirements

- **FR-001**: All text-editing inputs (text, number, search, email, password, textarea, select) MUST share a single unified visual style defined by a consistent set of CSS design tokens.
- **FR-002**: Every text input MUST have a visible boundary — either a border or sufficient background contrast against its container — so users can identify editable fields without relying on interaction.
- **FR-003**: Every input MUST inherit theme color tokens (`--surface-2`, `--text`, `--text-tertiary`, `--accent`) so it adapts when a behavioral theme changes those token values.
- **FR-004**: The focus indicator MUST use `:focus-visible` (not `:focus`) so the accent-colored ring appears only on keyboard navigation, keeping mouse/tap interactions visually clean. The indicator must be clearly visible across all themes.
- **FR-005**: Input placeholder text MUST use the theme's tertiary text color token and remain legible against the input background.
- **FR-006**: Inputs in light mode MUST remain visually distinguishable from their surrounding container (minimum 3:1 contrast ratio between input background and container background).
- **FR-007**: All previously orphan/unstyled input instances — `class="input"` in the config modal, bare `<input>` in the training parameter blocks, `login-card__input` on the login page, and the compute backend `<select>` with inline styles — MUST be migrated to the unified component class or receive equivalent styling.
- **FR-008**: Multi-line text entry controls (if any are added) MUST follow the same visual conventions as single-line inputs.
- **FR-009**: Under "Reduce effects" mode (maximum legibility), inputs MUST display with solid backgrounds, clear borders, and no decorative/animating effects regardless of the active theme.
- **FR-010**: Number inputs (`type="number"`) MUST be styled identically to text inputs in width, height, background, border, radius, and focus behavior.
- **FR-011**: Disabled inputs MUST render at reduced opacity (matching the existing button disabled pattern at ~0.4) with no focus ring and no hover effects.
- **FR-012**: Read-only inputs MUST use a subtly shifted background tone to indicate non-editable content, while retaining normal focus behavior and legibility.

### Key Entities

- **Select Component**: A dropdown selection element rendered as `<select>`. Should share the same visual language (background, border, radius, sizing, focus ring) as text inputs, with additional custom chevron styling.
- **Text Input Component**: Any single-line editable text field rendered as `<input type="text|number|search|email|password">` in the UI. Defined by background, border, radius, padding, font, placeholder, and focus ring.
- **Textarea Component**: A multi-line editable text field rendered as `<textarea>`. Should share the same visual language (border, radius, background, focus ring) as text inputs with additional line-height and resize behavior.
- **Input Theme Tokens**: A set of CSS custom properties (e.g., `--bg-input`, `--border-input`, `--focus-ring-input`) that themes can override to customize input appearance independently of other surface tokens. Alternatively, reuse existing tokens (`--surface-2`, `--accent`, `--text`, etc.) if they produce acceptable results across all themes.
- **Theme CSS Layer**: Behavioral theme CSS files optionally override input tokens so themed inputs are visually coherent with the rest of the themed UI.

## Success Criteria

### Measurable Outcomes

- **SC-001**: Every text-editing input and select across all template files uses the same CSS class or token set for background, border, radius, padding, font, and placeholder — verified by visual audit of all input instances.
- **SC-002**: All 23 behavioral themes produce readable, distinct text inputs (legible text, visible boundary, clear focus indicator) — verified by activating at least 5 representative themes (1 light-mode theme, 1 dark-only theme, 1 high-saturation theme, 1 low-contrast theme, and the default theme) and confirming inputs are usable in each.
- **SC-003**: The orphan `class="input"` input in the config modal, the `login-card__input` on the login page, and the 7 bare inputs in the training form are all migrated to the unified component — verified by visual inspection showing they match other app inputs.
- **SC-004**: In light mode, all text inputs maintain a visible boundary against their container — verified by visual inspection across all pages in light mode.
- **SC-005**: All text inputs meet the 44px minimum touch target — verified by measuring each distinct input type on a mobile-width viewport.

## Assumptions

- The existing design system token structure (`--surface-2`, `--text`, `--accent`, `--radius`, etc.) can adequately drive input appearance across themes without a new dedicated token layer.
- The `.form-input` CSS class (defined in `components.css`) is the correct target for unification — it is already the most widely used input class.
- The `training.html` param-block styling can be adapted to use the base input class without breaking the param-block layout.
- No new third-party dependencies are needed — this is a pure CSS/HTML change within the existing stack.
- The config modal's `class="input"` reference was an oversight during refactoring and should simply be changed to `class="form-input"`.
- All behavioral themes use CSS custom property overrides, so inputs that reference those properties will automatically adapt — no individual theme-level overrides are needed unless a theme cannot produce acceptable results from the base tokens alone.
