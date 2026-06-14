---
name: microgpt-workbench
colors:
  primary: "#3B82F6"
  secondary: "#8A8C94"
  tertiary: "#34D399"
  neutral: "#0E0F12"
  surface: "#181A1F"
  on-surface: "#E8EAED"
  error: "#EF4444"
  warning: "#F59E0B"
  info: "#38BDF8"
  accent-magenta: "#A78BFA"
  on-primary: "#FFFFFF"
  neutral-light: "#FAFAFA"
  surface-light: "#FFFFFF"
  on-surface-light: "#16181D"
  border: "#2A2C32"
  border-light: "#E4E5E7"
typography:
  display:
    fontFamily: Times New Roman, Georgia, serif
    fontSize: 2rem
    fontWeight: 700
    lineHeight: 1.2
  headline-lg:
    fontFamily: -apple-system, BlinkMacSystemFont, Segoe UI, Roboto, sans-serif
    fontSize: 1.1rem
    fontWeight: 700
    lineHeight: 1.3
    letterSpacing: 0.02em
  headline-md:
    fontFamily: -apple-system, BlinkMacSystemFont, Segoe UI, Roboto, sans-serif
    fontSize: 1rem
    fontWeight: 700
    lineHeight: 1.3
  headline-sm:
    fontFamily: -apple-system, BlinkMacSystemFont, Segoe UI, Roboto, sans-serif
    fontSize: 0.78rem
    fontWeight: 600
    lineHeight: 1.4
    letterSpacing: 0.03em
    textTransform: uppercase
  body-lg:
    fontFamily: -apple-system, BlinkMacSystemFont, Segoe UI, Roboto, sans-serif
    fontSize: 0.9rem
    fontWeight: 400
    lineHeight: 1.7
  body-md:
    fontFamily: -apple-system, BlinkMacSystemFont, Segoe UI, Roboto, sans-serif
    fontSize: 0.85rem
    fontWeight: 400
    lineHeight: 1.6
  body-sm:
    fontFamily: -apple-system, BlinkMacSystemFont, Segoe UI, Roboto, sans-serif
    fontSize: 0.72rem
    fontWeight: 400
    lineHeight: 1.5
  label-lg:
    fontFamily: SF Mono, Fira Code, Cascadia Code, JetBrains Mono, monospace
    fontSize: 0.85rem
    fontWeight: 400
    lineHeight: 1.4
  label-md:
    fontFamily: SF Mono, Fira Code, Cascadia Code, JetBrains Mono, monospace
    fontSize: 0.65rem
    fontWeight: 600
    lineHeight: 1.3
    letterSpacing: 0.05em
    textTransform: uppercase
  label-sm:
    fontFamily: SF Mono, Fira Code, Cascadia Code, JetBrains Mono, monospace
    fontSize: 0.6rem
    fontWeight: 600
    lineHeight: 1.3
    letterSpacing: 0.05em
    textTransform: uppercase
rounded:
  none: 0
  sm: 4px
  md: 8px
  lg: 16px
spacing:
  xs: 4px
  sm: 8px
  md: 16px
  lg: 24px
  xl: 48px
  xxl: 96px
motion:
  ease: cubic-bezier(0.4, 0, 0.2, 1)
  dur-fast: 150ms
  dur-slow: 400ms
components:
  button-primary:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.on-primary}"
    typography: "{typography.body-md}"
    rounded: "{rounded.md}"
    padding: 5px 16px
  button-primary-hover:
    backgroundColor: "#2563EA"
  button-primary-disabled:
    backgroundColor: transparent
    textColor: "{colors.secondary}"
    rounded: "{rounded.md}"
    padding: 5px 16px
  button-outline:
    backgroundColor: transparent
    textColor: "{colors.primary}"
    typography: "{typography.body-md}"
    rounded: "{rounded.md}"
    padding: 5px 16px
  button-outline-hover:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.neutral}"
  button-success:
    backgroundColor: transparent
    textColor: "{colors.tertiary}"
    typography: "{typography.body-md}"
    rounded: "{rounded.md}"
    padding: 5px 16px
  button-success-hover:
    backgroundColor: "{colors.tertiary}"
    textColor: "{colors.neutral}"
  button-error:
    backgroundColor: transparent
    textColor: "{colors.error}"
    typography: "{typography.body-md}"
    rounded: "{rounded.md}"
    padding: 5px 16px
  button-error-hover:
    backgroundColor: "{colors.error}"
    textColor: "{colors.neutral}"
  button-warning:
    backgroundColor: transparent
    textColor: "{colors.warning}"
    typography: "{typography.body-md}"
    rounded: "{rounded.md}"
    padding: 5px 16px
  button-warning-hover:
    backgroundColor: "{colors.warning}"
    textColor: "{colors.neutral}"
  card:
    backgroundColor: "{colors.surface}"
    typography: "{typography.body-sm}"
    rounded: "{rounded.md}"
    padding: "{spacing.md}"
  card-header:
    backgroundColor: "var(--bg-element)"
    typography: "{typography.label-md}"
    rounded: "{rounded.md}"
    padding: 8px 14px
  panel:
    backgroundColor: "var(--bg-panel)"
    rounded: "{rounded.md}"
    padding: "{spacing.lg}"
  input:
    backgroundColor: "{colors.neutral}"
    textColor: "{colors.on-surface}"
    typography: "{typography.label-lg}"
    rounded: "{rounded.md}"
    padding: 3px 8px
  input-focus:
    borderColor: "{colors.primary}"
  badge:
    backgroundColor: transparent
    textColor: "{colors.secondary}"
    typography: "{typography.label-sm}"
    rounded: "{rounded.sm}"
    padding: 1px 6px
  badge-success:
    textColor: "{colors.tertiary}"
  badge-warning:
    textColor: "{colors.warning}"
  badge-error:
    textColor: "{colors.error}"
  badge-info:
    textColor: "{colors.info}"
  toast:
    backgroundColor: "var(--bg-panel)"
    textColor: "{colors.on-surface}"
    typography: "{typography.body-sm}"
    rounded: "{rounded.md}"
    padding: 8px 14px
  toast-success:
    borderColor: "{colors.tertiary}"
    textColor: "{colors.tertiary}"
  toast-error:
    borderColor: "{colors.error}"
    textColor: "{colors.error}"
  toast-info:
    borderColor: "{colors.info}"
    textColor: "{colors.info}"
---
## Overview

microgpt-workbench is an interactive ML learning tool that wraps Karpathy's microgpt.py with a live training dashboard, experiment tracking, and explorable concept pages. The design language is **editorial whimsy** — imagined as a cross between a mid-century textbook publisher's typesetting and a modern terminal emulator.

The personality is warm, precise, and slightly playful. Dark backgrounds with bright accent colors create a focus-forward environment for watching loss curves tick. Serif display type adds gravitas to concept headings. Monospace consistently signals "this is data" — tokens, tensor values, code blocks, and step counts all speak in the same typeface.

**Brand keywords**: educational, precise, warm, slightly quirky, data-literate.

## Colors

The palette is deliberately restrained. A near-black background (`neutral`) creates a cinema-dark canvas. The primary electric blue (`primary`) is reserved exclusively for interactive elements — buttons, links, active states, focus rings. It means "things you can touch." Never use primary for body text or decorative borders.

Supporting accents serve single semantic jobs:
- **Tertiary (green)**: success states, completed training runs, positive metrics
- **Warning (amber)**: degraded states, warnings, caution indicators
- **Error (red)**: failures, errors, stopped services
- **Info (cyan)**: informational highlights, links to documentation, help text
- **Accent-magenta**: section separators, special decorative labels

The secondary color handles all non-interactive supporting text — parameter descriptions, help text, hints, metadata. It sits visibly below the primary text color but still reads clearly.

### Light mode

The light palette inverts the background/surface relationship while preserving all semantic accent colors (slightly desaturated for legibility on white). The near-black primary becomes a slightly deeper blue. The warm character is preserved through the amber warning and info cyan tones.

### Mode switching

The system respects three paths to theme switching, in priority order:
1. **Explicit user choice**: stored in `localStorage` as `theme=dark|light`, applied via `data-theme` attribute on `<html>`
2. **OS preference**: `prefers-color-scheme: dark` media query when no explicit choice is stored
3. **Default**: dark mode

All component styles respond to the `data-theme` attribute. No component file contains mode-specific hex values — those live exclusively in the token definitions.

### Accessibility

All text/background pairs must meet WCAG AA contrast (4.5:1 minimum for normal text, 3:1 for large text). The primary accent on neutral (#3B82F6 on #0E0F12) exceeds this threshold. Secondary text (#8A8C94 on #0E0F12) passes at 6.7:1.

## Typography

Three type families serve three distinct roles, never mixed:

| Family | Role | Where Used |
|--------|------|------------|
| **Times New Roman / Georgia** (serif) | Display — editorial weight | Concept page step titles, feature headers (`.terminal-h1` via display font) |
| **System sans-serif** (body) | Reading — all prose | Body text, labels, buttons, tables, form inputs, navigation |
| **SF Mono / Fira Code / JetBrains Mono** (mono) | Data — everything computed | Token values, tensor scalars, loss numbers, code blocks, badges, status indicators |

### Scale

The type scale has ten levels but most pages use only four or five:

- **`display`**: Full-width concept page headers. Use sparingly — one per page.
- **`headline-lg`**: Section titles (e.g., "1. Select Your Data"). Always uppercase, always bordered below.
- **`headline-md`**: Subsection titles. Uses primary color for hierarchy.
- **`headline-sm`**: Minor section labels. All caps, muted color, light tracking.
- **`body-lg`**: Narrative text — step descriptions in concept pages.
- **`body-md`**: Default body — buttons, table cells, labels.
- **`body-sm`**: Compact text — help text, parameter descriptions, hints.
- **`label-lg`**: Large mono — input values, data display.
- **`label-md`**: Mono labels — panel titles, data source labels. All caps with tracking.
- **`label-sm`**: Small mono — badges, pill labels, tiny status text.

The base font size on `<html>` is 20px (scales down to 17px on tablets, 16px on phones). All rem values cascade from this.

## Layout & Spacing

### App shell

Every page lives inside a shared app shell with three structural layers:

1. **Header** (sticky, top): Logo (`microgpt` + version), navigation tabs with divider separators, theme toggle button, ops dashboard link
2. **Main** (scrollable, center): Content area with `max-width: 1200px`, auto-centered
3. **Status bar** (sticky, bottom): System status ("ONLINE"), live clock, uptime, model/experiment/dataset counts

### Page archetypes

Pages follow four layout archetypes — no per-route bespoke layouts:

- **Archetype A (Concept)**: Two-column scroll scene — sticky visual pane (left/right) + scrolling narrative (right/left). Used for learn pages (tokenization, embeddings, attention, etc.)
- **Archetype B (Dashboard)**: Multi-row grid — data source panel, config panel, chart, metrics, samples. Used for training, datasets, operations
- **Archetype C (List/Detail)**: Table with selection → detail drill-down. Used for experiments, models
- **Archetype D (Playground)**: Single-column sandbox. Used for inference/playground

### Spacing scale

The modular spacing scale follows a roughly 1.5× multiplier from `sm` upward. Use the defined steps — never invent values between them:

- **`xs` (4px)**: Inner gaps in chips, token lists, badge text padding
- **`sm` (8px)**: Tight element gaps, chip spacing, form element padding
- **`md` (16px)**: Default component padding, card internal gutters, grid gaps
- **`lg` (24px)**: Section spacing, panel padding, button group separation
- **`xl` (48px)**: Major section breaks, page padding on desktop
- **`xxl` (96px)**: Large narrative spacing in concept pages

### Responsive behavior

- **≤768px** (tablet): Base font drops to 17px. Side-by-side layouts collapse to single column. Nav tabs wrap to full width. Sticky visuals become inline stacked.
- **≤480px** (phone): Base font drops to 16px. Minimal padding. Tables may scroll horizontally.

## Elevation & Depth

The design uses minimal depth cues. Cards and panels sit flat on the surface — no drop shadows by default. When visual separation is needed between a card and the background, use a `1px solid var(--border)` border rather than a shadow.

The only exception is the `.panel` component in the legacy system, which uses a subtle `box-shadow: 0 1px 3px rgba(0,0,0,0.2)`. New components should prefer the flat approach with border separation.

Depth is communicated through color contrast (surface vs. background, accent vs. muted) rather than through shadow or z-index layers.

## Shapes

Border radius is uniform across all interactive and container elements — 8px (`rounded: md`). This applies to buttons, inputs, panels, cards, badges, toasts, and dropdowns.

Smaller radii are used sparingly:
- **4px (`sm`)**: Badges, progress bars, code inline backgrounds
- **16px (`lg`)**: Reserved for special decorative containers (not currently used)

The `none` value is used for elements that should be sharp-cornered (status bars, header bottom edge).

## Components

### Buttons

Buttons are outlined by default — transparent background with a colored border. On hover, the background fills with the border color and the text inverts to the background color. This creates a consistent "reveal" interaction across all button variants.

**Primary buttons** (`button-primary`): Electric blue border and text. Hover fills blue, text goes dark. The primary action on any page. Use one per viewport section maximum.

**Outline buttons** (`button-outline`): Same pattern as primary but serves as the default/secondary action. Used for less prominent CTAs.

**Semantic buttons** (`button-success`, `button-error`, `button-warning`): Follow the same outline → fill pattern but with semantic accent colors. Use `success` for start/resume actions, `error` for stop/delete actions, `warning` for restart/retry actions.

**Button sizes**: Default padding is `5px 16px`. Small variant (`btn-action`/`btn-sm`) uses `2px 8px` for inline actions in tables and htop rows.

**Disabled state**: Opacity 0.35, `not-allowed` cursor. Hover doesn't fill. Borders and text revert to muted gray. Prevents ambiguity — a disabled button is visually unmistakable.

### Cards & Panels

**Cards** (`card`): Simple bordered containers on the surface color. No shadow. Internal padding of `16px` (`spacing: md`). Used for data source summaries, model info, strategy selection.

**Panels** (`panel`): Larger structural containers that form the primary layout units of dashboard pages. May have an optional header with title and icon.

### Forms

**Inputs** (`input`): Dark background (matching the page background), bordered, monospace font for data entry. Focus state shows a 2px accent outline with 2px offset — never a fuzzy box-shadow.

**Selects**: Custom-styled with an SVG chevron icon replacing the native dropdown arrow. Same border/focus pattern as inputs.

**Sliders**: Use native `accent-color: var(--accent)` for cross-browser consistency.

**File inputs**: Custom file selector button with the same outline → fill hover as semantic buttons. File name display to the right of the button.

### Badges & Pills

Badges are small, uppercase, monospace labels used for status indication and categorization. They follow the outline pattern (colored border, colored text, transparent background) matching the button system.

Four semantic badge colors map to the accent system:
- **Badge-info (cyan)**: Corpus labels, data type indicators
- **Badge-success (green)**: Dataset labels, positive status
- **Badge-warning (amber)**: Degraded states
- **Badge-error (red)**: Error status
- **Badge-magenta**: Special category labels

### Toasts

Notification toasts slide in from the bottom-right with a brief animation (`translateX(20px) → translateX(0)` over 250ms). They auto-dismiss — unless they're error toasts, which persist until dismissed.

Three toast variants match the semantic system:
- **Toast-success**: Green border and text
- **Toast-error**: Red border and text
- **Toast-info**: Cyan/blue border and text

### Tables

Tables use uppercase monospace headers with generous tracking. Rows are separated by subtle borders. Row hover highlights the entire row background. This is a "data table" — it looks like something from `psql` or `htop`, not a spreadsheet.

### Spinner

The spinner is text-based (cycling `| / - \` characters) in info-cyan. No animated SVG or CSS-only rotation circles. The text spinner is smaller, less distracting, and tonally consistent with the terminal-influenced design.

## Motion

Animations serve a functional purpose: orienting the user to state changes. They are never decorative.

- **`dur-fast` (150ms)**: Hover states, focus rings, color transitions on buttons/links/badges
- **`dur-slow` (400ms)**: Toast entrance, panel visibility toggles, resource bar width changes
- **Easing**: `cubic-bezier(0.4, 0, 0.2, 1)` — smooth ease-out with gentle deceleration

### Reduced motion

When `prefers-reduced-motion: reduce` is active, ALL transitions and animations are disabled via `transition: none !important; animation: none !important;`. State changes become instant. No information is lost — motion was never carrying semantic content.

## Do's and Don'ts

- **Do** use the primary accent for interactive elements only. One interactive accent per viewport section maximum.
- **Do** use monospace for all data display — token values, tensor scalars, loss numbers, code blocks, step counts, table content.
- **Do** use the spacing scale strictly. Never invent spacing values between `xs/sm/md/lg/xl/xxl`.
- **Do** use body (sans-serif) for all prose and labels. Serif display is for concept page headers only.
- **Do** use the outline → fill hover pattern for all buttons. Maintains a consistent interaction language.
- **Do** respect WCAG AA contrast (4.5:1 minimum) for all text/background pairs in both modes.
- **Do** use `data-theme="dark|light"` attribute for mode switching. Never use a separate CSS file per theme.
- **Don't** use the primary accent for body text, static borders, or decorative surfaces.
- **Don't** use serif fonts for body text, labels, buttons, or data. Serif is display-only.
- **Don't** mix font families in the same text element. Each typography level has exactly one family.
- **Don't** add drop shadows to cards. Use border separation instead.
- **Don't** use `@ts-ignore`, `as any`, or hardcoded hex values in component code. All values reference tokens.
- **Don't** use inline styles in Jinja2 templates for colors, spacing, or typography. Token variables or utility classes only.
- **Don't** create new bespoke page layouts. Every page must fit into one of the four archetypes.
- **Don't** suppress reduced-motion preferences. All transitions must respect `prefers-reduced-motion`.