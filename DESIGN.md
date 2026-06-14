---
name: anvil
platform: ios
version: 2.0.0

## iOS Design Tokens (Dark)
colors:
  bg: "#000000"            # iOS dark system background
  surface: "#1c1c1e"       # iOS dark secondary surface (grouped table background)
  surface-secondary: "#2c2c2e"  # iOS dark tertiary surface
  grouped-bg: "#0c0c0d"    # iOS dark grouped background
  separator: "#38383a"     # iOS dark separator
  text: "#ffffff"           # iOS dark label
  text-secondary: "#ebebf5" # iOS dark secondary label (88% opacity equivalent)
  text-tertiary: "#8e8e93"  # iOS dark tertiary label
  accent: "#007aff"        # iOS system blue
  accent-green: "#34c759"   # iOS system green
  accent-red: "#ff3b30"     # iOS system red
  accent-orange: "#ff9500"  # iOS system orange
  accent-yellow: "#ffcc00"  # iOS system yellow
  accent-purple: "#af52de"  # iOS system purple
  accent-cyan: "#32d74b"    # iOS system cyan (mapped)
  fill-primary: "#787880"   # iOS fill (58% opacity white)
  fill-secondary: "#686870" # iOS secondary fill
  glass-bg: "rgba(28, 28, 30, 0.85)"    # dark nav bar glass
  glass-blur: "sat(180%) blur(20px)"
  shadow: "rgba(0, 0, 0, 0.3)"

## iOS Design Tokens (Light)
colors-light:
  bg: "#f2f2f7"            # iOS light grouped background
  surface: "#ffffff"        # iOS light surface
  surface-secondary: "#f2f2f7"  # iOS light secondary surface
  grouped-bg: "#f2f2f7"     # iOS light grouped background
  separator: "#c6c6c8"      # iOS light separator
  text: "#000000"           # iOS light label
  text-secondary: "#3c3c43" # iOS light secondary label (60% opacity equivalent)
  text-tertiary: "#8e8e93"  # iOS light tertiary label
  accent: "#007aff"         # iOS system blue
  accent-green: "#34c759"
  accent-red: "#ff3b30"
  accent-orange: "#ff9500"
  accent-yellow: "#ffcc00"
  accent-purple: "#af52de"
  accent-cyan: "#32d74b"
  fill-primary: "#787880"
  fill-secondary: "#686870"
  glass-bg: "rgba(255, 255, 255, 0.72)"  # iOS light nav bar
  glass-blur: "sat(180%) blur(20px)"
  shadow: "rgba(0, 0, 0, 0.1)"

typography:
  large-title:
    fontFamily: -apple-system, BlinkMacSystemFont, system-ui, sans-serif
    fontSize: "2rem"       # 34px @ 17px base
    fontWeight: 700
    lineHeight: 1.2
  title-1:
    fontFamily: -apple-system, BlinkMacSystemFont, system-ui, sans-serif
    fontSize: "1.65rem"    # 28px
    fontWeight: 400
    lineHeight: 1.3
  title-2:
    fontFamily: -apple-system, BlinkMacSystemFont, system-ui, sans-serif
    fontSize: "1.3rem"     # 22px
    fontWeight: 400
    lineHeight: 1.3
  title-3:
    fontFamily: -apple-system, BlinkMacSystemFont, system-ui, sans-serif
    fontSize: "1.18rem"    # 20px
    fontWeight: 600
    lineHeight: 1.3
  headline:
    fontFamily: -apple-system, BlinkMacSystemFont, system-ui, sans-serif
    fontSize: "0.94rem"    # 16px @ 17px
    fontWeight: 600
    lineHeight: 1.3
  body:
    fontFamily: -apple-system, BlinkMacSystemFont, system-ui, sans-serif
    fontSize: "0.94rem"    # 16px
    fontWeight: 400
    lineHeight: 1.5
  callout:
    fontFamily: -apple-system, BlinkMacSystemFont, system-ui, sans-serif
    fontSize: "0.88rem"    # 15px
    fontWeight: 400
    lineHeight: 1.4
  subhead:
    fontFamily: -apple-system, BlinkMacSystemFont, system-ui, sans-serif
    fontSize: "0.82rem"    # 14px
    fontWeight: 400
    lineHeight: 1.4
  footnote:
    fontFamily: -apple-system, BlinkMacSystemFont, system-ui, sans-serif
    fontSize: "0.76rem"    # 13px
    fontWeight: 400
    lineHeight: 1.4
  caption-1:
    fontFamily: -apple-system, BlinkMacSystemFont, system-ui, sans-serif
    fontSize: "0.71rem"    # 12px
    fontWeight: 400
    lineHeight: 1.3
  caption-2:
    fontFamily: -apple-system, BlinkMacSystemFont, system-ui, sans-serif
    fontSize: "0.65rem"    # 11px
    fontWeight: 400
    lineHeight: 1.3
  mono:
    fontFamily: ui-monospace, SF Mono, Menlo, Monaco, Cascadia Code, Consolas, monospace
    fontSize: "0.88rem"
    fontWeight: 400
    lineHeight: 1.4

rounded:
  sm: 8px
  md: 13px                # iOS standard corner radius
  lg: 20px                # iOS card corner radius
  xl: 30px                # iOS pill radius

spacing:
  xs: 4px
  sm: 8px
  md: 16px
  lg: 20px
  xl: 24px
  xxl: 32px

motion:
  spring-quick: linear(0, 0.006, 0.025 2.2%, 0.104 5.6%, 0.467 14.3%, 0.752 22.5%, 0.896 29.7%, 0.981 36.7%, 1.016 43.7%, 1.012 52.5%, 0.938 66.2%, 0.867 79.6%, 0.83 89.9%, 0.819 100%);   # iOS spring (enter)
  spring-slow: linear(0, 0.009 18.2%, 0.584 40.9%, 0.898 57.7%, 1.016 73.9%, 0.991 91.4%, 1);  # iOS spring (exit/present)
  dur-fast: 200ms
  dur-slow: 400ms
  ease: cubic-bezier(0.32, 0.94, 0.6, 1)  # iOS standard ease

---

## Overview

anvil is an interactive ML learning tool that wraps Karpathy's microgpt.py with a live training dashboard, experiment tracking, and explorable concept pages. The design language is **iOS modern** — imagined as a native iOS app brought to the web.

The personality is clean, precise, and responsive. Light and dark modes follow Apple's system color semantics. Glass navigation bars provide depth hierarchy. Spring animations make interactions feel tactile. System sans-serif typography ensures maximum readability across all devices.

**Brand keywords**: clean, precise, responsive, tactile, data-literate, native-feeling.

## Colors

The palette follows Apple's iOS Human Interface Guidelines for both light and dark mode. The system blue (`#007aff`) is the primary interactive color — buttons, links, active states, and focus rings. It means "things you can touch." Never use primary for body text or decorative borders.

### Dark Mode
- **Background** (`#000000`): True black — OLED-friendly for mobile devices, rich contrast for data display
- **Surface** (`#1c1c1e`): Cards, panels, and grouped containers
- **Secondary surface** (`#2c2c2e`): Deeper nesting of grouped content
- **Separator** (`#38383a`): Thin hairline borders between grouped list rows

### Light Mode
- **Background** (`#f2f2f7`): Light gray grouped background (standard iOS light mode)
- **Surface** (`#ffffff`): Cards, panels, and list sections
- **Secondary surface** (`#f2f2f7`): Match background for seamless grouping
- **Separator** (`#c6c6c8`): Light separator between rows

### Semantic Accents
System colors serve single semantic jobs:
- **Blue (system)**: Interactive elements, links, active states, primary actions
- **Green (system)**: Success states, completed training runs, positive metrics, start actions
- **Red (system)**: Errors, failures, destructive actions, stop buttons
- **Orange (system)**: Warnings, degraded states, caution indicators, retry actions
- **Yellow (system)**: Warnings, attention indicators
- **Purple (system)**: Special labels, section markers

### Mode switching
The system respects three paths to theme switching, in priority order:
1. **Explicit user choice**: stored in `localStorage` as `theme=dark|light`, applied via `data-theme` attribute on `<html>`
2. **OS preference**: `prefers-color-scheme: dark` media query when no explicit choice is stored
3. **Default**: dark mode

All component styles respond to the `data-theme` attribute. No component file contains mode-specific hex values — those live exclusively in the token definitions.

### Accessibility
All text/background pairs must meet WCAG AA contrast (4.5:1 minimum for normal text, 3:1 for large text). The glass nav bar uses an 85% opacity dark scrim / 72% opacity light scrim to ensure text contrast against variable backgrounds. Never place text over a pure `backdrop-filter` blur without a solid/scrim backing layer.

## Typography

The type system follows Apple's iOS type scale with a single type family:

| Style | Size (rem) | Weight | Where Used |
|-------|-----------|--------|------------|
| **Large Title** | 2.0rem (34px) | Bold | Page headers, screen titles |
| **Title 1** | 1.65rem (28px) | Regular | Section headers in content |
| **Title 2** | 1.3rem (22px) | Regular | Subsection headers |
| **Title 3** | 1.18rem (20px) | Semibold | Card titles, panel headers |
| **Headline** | 0.94rem (16px) | Semibold | Bold body, key metrics |
| **Body** | 0.94rem (16px) | Regular | Default body text |
| **Callout** | 0.88rem (15px) | Regular | Secondary content |
| **Subhead** | 0.82rem (14px) | Regular | Tertiary content |
| **Footnote** | 0.76rem (13px) | Regular | Captions, help text |
| **Caption 1** | 0.71rem (12px) | Regular | Small labels, timestamps |
| **Caption 2** | 0.65rem (11px) | Regular | Tiny status, badges |
| **Mono** | 0.88rem | Regular | Code, data values, metrics |

### Font Selection
- **Body/UI**: `-apple-system, BlinkMacSystemFont, system-ui, sans-serif` — resolves to SF Pro on Apple devices
- **Mono**: `ui-monospace, SF Mono, Menlo, Monaco, Cascadia Code, Consolas, monospace`
- SF Pro is NOT embedded via `@font-face` due to Apple's licensing restrictions

### Scale
The base font size on `<html>` is 17px (down from the current 20px) — matching iOS's standard body text size. It scales down to 16px on phones.

## Layout & Spacing

### App shell
Every page lives inside a shared app shell with three structural layers:

1. **Navigation bar** (sticky, top): Large title (left), theme toggle (right), glass backdrop. Title collapses to inline when scrolled (standard iOS navigation bar behavior).
2. **Main** (scrollable, center): Content area with padding matching iOS standard margins (16px on each side)
3. **Tab bar** (sticky, bottom): Scrollable tab bar with all navigation items. Glass backdrop. `100dvh` flexbox layout with `env(safe-area-inset-bottom)` for home indicator clearance.

### Page archetypes
Pages follow four layout archetypes:

- **Archetype A (Single Column)**: Full-width content with iOS grouped sections. Used for concept pages, FAQ, learn index.
- **Archetype B (Dashboard)**: Multi-section vertical stack with optional side-by-side on wider screens. Used for training, operations.
- **Archetype C (List/Detail)**: iOS grouped table view with selection → detail drill-down. Used for experiments, models, datasets.
- **Archetype D (Playground)**: Single-column sandbox with grouped form sections. Used for inference/playground.

### Spacing scale
The spacing scale follows iOS's 8px grid:

- **`xs` (4px)**: Inner gaps in chips, token lists
- **`sm` (8px)**: Tight element gaps, chip spacing, form element padding — base grid unit
- **`md` (16px)**: Default component padding, card internal gutters, page margins
- **`lg` (20px)**: Section spacing, panel padding
- **`xl` (24px)**: Major section breaks, large button padding
- **`xxl` (32px)**: Large narrative spacing

### Safe areas
All layouts use `env(safe-area-inset-*)` variables for iOS PWA and notch support:
- Top nav bar: `padding-top: env(safe-area-inset-top)`
- Bottom tab bar: `padding-bottom: env(safe-area-inset-bottom)`
- Page content: standard padding (safe areas handled by nav/tab bars)

### Responsive behavior
- **≤768px** (tablet/phone): Base font stays at 17px. Side-by-side layouts collapse to single column. Standard iOS margins.
- **≤480px** (phone): Base font drops to 16px. Tighter margins (12px). Tab bar labels may shorten.

## Elevation & Depth

Depth is communicated through glass materials and subtle shadows, not through heavy borders.

### Glass Navigation
The navigation bar and tab bar use `backdrop-filter: saturate(180%) blur(20px)` with a translucent backing (`rgba(28, 28, 30, 0.85)` in dark, `rgba(255, 255, 255, 0.72)` in light). This creates the standard iOS frosted glass effect.

### Glass Fallback
When `backdrop-filter` is unsupported or `prefers-reduced-transparency` is active, both bars fall back to solid `--surface` background with a 1px bottom/top separator border. No information is lost.

### Cards & Panels
Cards use subtle shadows (iOS material shadow) rather than borders:
- Dark: `0 1px 3px rgba(0,0,0,0.3)`
- Light: `0 1px 3px rgba(0,0,0,0.1)`

### Shadows
- `shadow-sm`: Small cards, buttons (0 1px 2px)
- `shadow-md`: Panels, modals (0 2px 8px)
- `shadow-lg`: Sheets, overlays (0 4px 16px)

## Shapes

Border radius follows iOS conventions:

| Size | Value | Where Used |
|------|-------|------------|
| **sm** (8px) | Buttons, inputs, small badges | Interactive elements |
| **md** (13px) | Cards, panels, grouped list rows | Standard iOS card radius |
| **lg** (20px) | Large cards, modal sheets | Featured containers |
| **xl** (30px) | Pills, tags, circular icons | Special decorative use |

## Components

### Navigation Bar
Large title on the left, theme toggle on the right. Glass backdrop (`backdrop-filter`). When the user scrolls, the large title should collapse to a standard inline title (handled via JS `IntersectionObserver` on the title element). Bottom border separator when scrolled.

### Tab Bar
Scrollable bottom tab bar with all navigation items. Each tab shows an SF Symbols-style icon (emoji/unicode symbol as placeholder) + label. Active tab shows the accent color. Glass backdrop. `env(safe-area-inset-bottom)` clearance.

- Tab labels are 10-11px (caption-2)
- Minimum tab width accommodates label + icon
- Tabs are `<a href>` elements for proper accessibility
- Active tab has colored icon + label

### Buttons
iOS-style system buttons:

**Primary (filled)**: Blue background, white text. The primary action on any screen. Rounded (13px). Height: 44px (touch target minimum). Use one per viewport section.

**Secondary (gray)**: Light gray fill in dark mode, light fill in light mode. Gray text. For less prominent actions.

**Semantic**: Filled with semantic colors — green for start, red for stop/destructive, orange for retry. Same shape as primary.

**Plain/Tertiary**: Text-only or tinted with no fill. For least prominent actions.

### Grouped List (iOS)
The primary data layout pattern. Replaces the current table/panel/htop patterns:

- Sections are separated by `--separator` color
- Each section has an optional header (uppercase, caption-1 weight, `--text-tertiary`)
- Rows have 13px corner radius, separated by hairline borders
- Row height: 44px minimum
- Optional accessory icons (chevron, toggle, badge)
- Content inset matches standard iOS (16px left/right)

### Cards
Rounded (13px) containers on `--surface` background. Subtle shadow. Internal padding of 16px. Used for data source summaries, model info blocks, metric displays.

### Forms
iOS-style form inputs:
- **Text inputs**: Rounded (13px), `--surface-secondary` background, inset appearance
- **Select menus**: System-like picker appearance
- **Sliders**: Native `accent-color: var(--accent)`
- **Toggles**: iOS switch appearance (custom CSS)
- **File inputs**: Styled as iOS document picker buttons

### Badges
Small rounded pills (13px or 20px radius) with colored background and white text. Inline with content. Unlike the previous outline badges, iOS badges are filled.

- Success: green fill
- Error: red fill  
- Warning: orange fill
- Info: blue fill
- Neutral: gray fill

### Toasts
iOS notification-style banners that slide down from the top of the screen (not from the bottom-right as before). Same semantic colors. Banner width matches the screen width on mobile, max 400px on desktop.

### Tables
iOS grouped table style:
- Sections with rounded corners
- Rows with separators
- Sticky section headers
- Selection highlights

### Spinner
Single rotating loading indicator using the standard iOS activity indicator style (a spinning circle via CSS animation, not the ASCII text spinner). Uses `--accent` color.

## Motion

### Spring Animations
Animations use CSS `linear()` timing functions that produce iOS-style spring overshoot:

- **Entrance** (spring-quick): Elements entering the screen or appearing (toasts, sheets, expanding sections). ~400ms with slight overshoot.
- **Exit** (spring-slow): Elements leaving the screen. ~350ms with deceleration.
- **Hover/Tap** (150ms, ease): Interactive state changes (button press, link hover, toggle switch).

### What Animates
- Button press → scale(0.97) with quick spring return
- Toast appearance → slide down from top with spring entrance
- Modal/sheet presentation → slide up with spring entrance
- Toggle switches → 200ms spring between on/off positions
- List row selection → brief highlight fade
- Section expansion → height + opacity transitions

### Reduced Motion
When `prefers-reduced-motion: reduce` is active, ALL transitions and animations are disabled via `transition: none !important; animation: none !important;`. State changes become instant. No information is lost — motion was never carrying semantic content.

### Reduced Transparency
When `prefers-reduced-transparency: reduce` is active, all `backdrop-filter` glass effects are replaced with solid `--surface` backgrounds. Nav bar and tab bar lose the blur but maintain the scrim color.

## Do's and Don'ts

- **Do** use the system blue accent for interactive elements only. One interactive accent per viewport section maximum.
- **Do** use `ui-monospace` for all data display — token values, tensor scalars, loss numbers, code blocks, step counts.
- **Do** use the 8px spacing grid strictly. Never invent spacing values between defined steps.
- **Do** use system sans-serif for ALL text. No serif or decorative fonts.
- **Do** use filled (not outlined) buttons as the primary button pattern.
- **Do** respect WCAG AA contrast (4.5:1 minimum) for all text/background pairs in both modes.
- **Do** use `data-theme="dark|light"` attribute for mode switching. Never use a separate CSS file per theme.
- **Do** use `backdrop-filter` with solid scrim backing for glass effects.
- **Do** use `env(safe-area-inset-*)` for iOS PWA/notch clearance.
- **Do** ensure minimum 44px touch targets on all interactive elements.
- **Don't** use the blue accent for body text, static borders, or decorative surfaces.
- **Don't** use serif fonts for anything.
- **Don't** use text-based ASCII spinners (| / - \). Use CSS spinning indicators.
- **Don't** use outlined buttons (fill → outline was the old pattern).
- **Don't** add drop shadows to nav bars or tab bars — use glass instead.
- **Don't** use `position: fixed; bottom: 0` for tab bars — use `100dvh` flexbox.
- **Don't** use `@font-face` to embed SF Pro.
- **Don't** apply `backdrop-filter` to more than 3 simultaneous surfaces.
- **Don't** create new bespoke page layouts. Every page must fit into one of the four archetypes.
- **Don't** suppress reduced-motion or reduced-transparency preferences.