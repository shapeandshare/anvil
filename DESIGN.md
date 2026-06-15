---
name: anvil
platform: ios
version: 2.1.0

## iOS Design Tokens (Dark)
colors:
  bg: "#000000"            # iOS dark system background
  surface: "#1c1c1e"       # iOS dark secondary surface (grouped table background)
  surface-2: "#2c2c2e"  # iOS dark tertiary surface
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
  glass-border: "rgba(255, 255, 255, 0.08)"
  shadow: "rgba(0, 0, 0, 0.3)"

## iOS Design Tokens (Light)
colors-light:
  bg: "#f2f2f7"            # iOS light grouped background
  surface: "#ffffff"        # iOS light surface
  surface-2: "#f2f2f7"  # iOS light secondary surface
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
  glass-border: "rgba(60, 60, 67, 0.12)"
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

anvil is an interactive ML learning tool for training and experimenting with small LLMs from scratch. It has evolved into a standalone engine (RoPE, SwiGLU, RMSNorm) with a live training dashboard, experiment tracking, and explorable concept pages. The design language is **iOS modern** — imagined as a native iOS app brought to the web.

The personality is clean, precise, and responsive. Light and dark modes follow Apple's system color semantics. Glass navigation bars provide depth hierarchy. Spring animations make interactions feel tactile. System sans-serif typography ensures maximum readability across all devices.

**Brand keywords**: clean, precise, responsive, tactile, data-literate, native-feeling, forged.

The hero/landing page uses a **forge** sub-theme — orange/amber glows, floating ember particles, and an anvil icon — that establishes the "forging intelligence" metaphor. This sub-theme is exclusive to the hero page; all other pages use the standard iOS palette with blue as the primary interactive color.

## Colors

The palette follows Apple's iOS Human Interface Guidelines for both light and dark mode. The system blue (`#007aff`) is the primary interactive color — buttons, links, active states, and focus rings. It means "things you can touch." Never use primary for body text or decorative borders.

The forge sub-theme (hero page only) elevates **orange** (`#ff9500`) and **yellow** (`#ffcc00`) as decorative brand colors — used for gradient text, ambient glow, ember particles, CTA accent, and decorative borders. On the hero page only, orange functions as a secondary brand accent; everywhere else it remains a warning color.

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
- **Orange (system)**: Warnings, degraded states, caution indicators, retry actions — also forge brand accent (hero page only)
- **Yellow (system)**: Warnings, attention indicators — also forge accent (hero page only)
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
The base font size on `<html>` is 17px — matching iOS's standard body text size. It scales down to 16px on phones.

## Layout & Spacing

### App shell
Every page lives inside a shared app shell with three structural layers:

1. **Navigation bar** (fixed top, glass): Horizontal scrollable tab strip (all nav items) with glass backdrop and vertical fade mask. Theme toggle button at the right. No large title — the nav bar is purely navigational. Height: `56px + env(safe-area-inset-top)`.
2. **Main** (scrollable, center): Content area with padding matching iOS standard margins (16px on each side). Has an ambient orange radial gradient at the top for depth.
3. **Footer**: Subtle centered footer with version, separated by a hairline rule. Uses `env(safe-area-inset-bottom)` for home indicator clearance.

The layout uses a `100dvh` flexbox column: `app-shell` → `app-main` (flex: 1, scrollable) → `site-footer` (flex-shrink: 0). No bottom tab bar exists — all navigation is in the top nav bar.

### Page archetypes
Pages follow five layout archetypes:

- **Archetype A (Single Column)**: Full-width content with iOS grouped sections. Used for concept pages, FAQ, learn index.
- **Archetype B (Dashboard)**: Multi-section vertical stack with optional side-by-side on wider screens. Used for training, operations.
- **Archetype C (List/Detail)**: iOS grouped table view with selection → detail drill-down. Used for experiments, models, datasets.
- **Archetype D (Playground)**: Single-column sandbox with grouped form sections. Used for inference/playground.
- **Archetype E (Hero/Landing)**: Centered single-column layout with forge visual elements (glow, embers, anvil icon), tagline, subtitle, CTA buttons, and a 2-column feature card grid. Used for the root `/` route only. Max-width: 720px. Content is vertically centered with generous top padding (`var(--space-8)`). Feature cards collapse to single column at ≤480px.

### Spacing scale
The spacing scale follows iOS's 8px grid with additional tokens for large spacing:

| Token | Value | Where Used |
|-------|-------|------------|
| `space-1` | 4px | Inner gaps in chips, token lists |
| `space-2` | 8px | Tight element gaps, chip spacing, base grid unit |
| `space-3` | 12px | Medium gaps, form element padding |
| `space-4` | 16px | Default component padding, card gutters, page margins |
| `space-5` | 20px | Section spacing, panel padding |
| `space-6` | 24px | Major section breaks, large button padding |
| `space-7` | 32px | Large narrative spacing |
| `space-8` | 48px | Hero section gaps, large vertical padding |
| `space-9` | 64px | Extra-large spacing, panel margins |
| `space-10` | 96px | Maximum spacing breaks |

### Safe areas
All layouts use `env(safe-area-inset-*)` variables for iOS PWA and notch support:
- Top nav bar: `padding-top: env(safe-area-inset-top)`
- Page content: `padding-top: calc(56px + env(safe-area-inset-top) + padding)` — safe areas handled by nav bar offset
- Footer: `padding-bottom: calc(tight-padding + env(safe-area-inset-bottom))`

### Responsive behavior
- **≤768px** (tablet/phone): Base font stays at 17px. Side-by-side layouts collapse to single column. Standard iOS margins.
- **≤480px** (phone): Base font drops to 16px. Tighter margins (12px). Hero title shrinks to 1.8rem. Feature cards collapse to single column. Forge icon shrinks to 2.8rem.

### Ambient background
Every page (via `base.css`) has:
- A **radial gradient** at the top of `.app-main`: `radial-gradient(ellipse 1200px 700px at 50% 8%, color-mix(in srgb, var(--accent-orange) 12%, transparent), transparent)` — a subtle orange glow at the top of the content area.
- **Floating ambient particles** in `.ambient-particles`: fixed-position, pointer-events-none ember-like circles that float upward from random positions across the viewport. 20 particles with varied delays and speeds (`--s: 6-12s`, `--d: 0-12s`). Warm variants glow with a yellow box-shadow. These are always present on every page.

## Elevation & Depth

Depth is communicated through glass materials, subtle shadows, and ambient glow — not through heavy borders.

### Glass Navigation
The navigation bar uses `backdrop-filter: saturate(180%) blur(20px)` with a translucent backing (`rgba(28, 28, 30, 0.85)` in dark, `rgba(255, 255, 255, 0.72)` in light). The glass has a **vertical fade mask**: `mask-image: linear-gradient(to bottom, black 0%, black 70%, transparent 100%)` — the glass effect fades out at the bottom of the nav bar. A subtle `--glass-border` provides the bottom edge definition.

### Glass Fallback
When `backdrop-filter` is unsupported or `prefers-reduced-transparency` is active, the nav bar falls back to solid `--surface` background with a 1px bottom separator. No information is lost.

### Forge Glow (Hero only)
The hero page's forge section has a pulsing orange radial glow behind the anvil icon: `radial-gradient(circle, color-mix(in srgb, orange 35%, transparent), transparent 70%)`. Animates via `forge-pulse`: scale(0.9→1.1), opacity(0.5→1), 3s infinite alternate.

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
Fixed top bar with inline horizontal-scrolling tab strip and a theme toggle button on the right. Glass backdrop (`backdrop-filter`) with vertical fade mask. Height: `56px + env(safe-area-inset-top)`.

- Tabs are `<a href>` elements with icon + label
- Active tab shows `--accent` color
- Tab labels: 0.65rem (caption-2 size)
- Tab icon: 1.2rem
- Scrollable on overflow with hidden scrollbar
- Theme toggle: `--surface-2` background, `--accent` color, 44px touch target

### Hero Page (Archetype E)

**Forge Section**: Centered hero block with:
- **Glow**: Pulsing orange radial glow behind the icon
- **Embers**: 8 floating particles (orange/yellow dots rising upward with varied timing), aria-hidden
- **Anvil icon**: Custom SVG of an anvil, `--accent-orange` color, drop-shadow glow, gentle bob animation (translateY -4px, 4s ease-in-out)
- **Title**: "anvil" in gradient text — `linear-gradient(135deg, orange, yellow)` with `background-clip: text`
- **Tagline**: "Forging intelligence." in `--accent-orange`, 1.15rem, fade-in animation
- **Subtitle**: Product description, `--text-secondary`, max-width 480px, fade-in animation (delayed)
- **Actions**: "Start Training" CTA (orange gradient button with glow box-shadow) + "Learn the Concepts" secondary button (surface-2), fade-in animation (delayed further)
- Feature cards: 2-column grid (`grid-template-columns: 1fr 1fr`), 7 feature cards (Data, Train, Experiments, Models, Play, Learn, Ops), each with SVG icon + title + description. Cards have staggered entrance animations via `--i` custom property. On hover: scale(1.05) + bounce animation + shadow-md.

**Responsive**: At ≤480px, feature cards collapse to 1 column, title shrinks to 1.8rem, gap/padding reduces, forge icon shrinks to 2.8rem.

### Buttons
iOS-style system buttons with forge variants:

**Primary (filled)**: Blue background, white text. The primary action on any screen. Rounded (13px). Height: 44px (touch target minimum). Use one per viewport section.

**Secondary (gray)**: Light gray fill in dark mode, light fill in light mode. Gray text. For less prominent actions.

**Semantic**: Filled with semantic colors — green for start, red for stop/destructive, orange for retry. Same shape as primary.

**Accent gradient** (`btn-accent`): Blue-to-purple gradient button for special call-to-action emphasis. Uses `linear-gradient(135deg, --accent, --accent-purple)`.

**Forge** (`btn--forge`, `hero-cta--forge`): Orange-to-yellow gradient button with glow box-shadow. Used exclusively on the hero page and forge-themed section cards. Optional pulse animation (`btn-pulse-forge`) for emphasis.

**Plain/Tertiary**: Text-only or tinted with no fill. For least prominent actions.

### Section Cards (Forge/Accent variants)
Cards used in content sections below the hero, with optional left accent border:
- `section-card--forge`: 3px orange left border
- `section-card--accent`: 3px blue left border
- Title variant `section-card__title--forge`: gradient text (orange→yellow)

### Grouped List (iOS)
The primary data layout pattern:

- Sections are separated by `--separator` color
- Each section has an optional header (uppercase, caption-1 weight, `--text-tertiary`)
- Rows have 13px corner radius, separated by hairline borders
- Row height: 44px minimum
- Optional accessory icons (chevron, toggle, badge)
- Content inset matches standard iOS (16px left/right)
- Staggered entrance animation via `--row-i`

### Cards
Rounded (13px) containers on `--surface` background. Subtle shadow. Internal padding of 16px. Used for data source summaries, model info blocks, metric displays. Staggered entrance animation via `--stagger-i`.

### Forms
iOS-style form inputs:
- **Text inputs**: Rounded (13px), `--surface-2` background, inset appearance
- **Select menus**: System-like picker appearance with custom chevron arrow
- **Sliders**: Native `accent-color: var(--accent)`
- **Toggles**: iOS switch appearance (custom CSS with slide thumb)
- **File inputs**: Styled as iOS document picker buttons

### Badges
Small rounded pills (13px or 20px radius) with colored background and white text. Inline with content. Filled style.

- Success: green fill
- Error: red fill  
- Warning: orange fill
- Info: blue fill
- Neutral: gray fill

### Toasts
iOS notification-style banners that slide down from the top of the screen. Semantic colors with tinted left border and gradient background. Banner width matches the screen width on mobile, max 400px on desktop.

### Tables
iOS grouped table style:
- Sections with rounded corners
- Rows with separators
- Sticky section headers
- Selection highlights
- Staggered row entrance animations

### Spinner
Single rotating loading indicator using the standard iOS activity indicator style (a spinning circle via CSS animation, not the ASCII text spinner). Uses `--accent` color. 20px, 2.5px border, 0.6s spin.

## Motion

### Spring Animations
Animations use CSS `linear()` timing functions that produce iOS-style spring overshoot:

- **Entrance** (spring-quick): Elements entering the screen or appearing (toasts, sheets, expanding sections, hero text fade-ins, card entrances). ~400ms with slight overshoot.
- **Exit** (spring-slow): Elements leaving the screen. ~350ms with deceleration.
- **Hover/Tap** (150ms, ease): Interactive state changes (button press, link hover, toggle switch).

### What Animates
- Button press → scale(0.97) with quick spring return
- Toast appearance → slide down from top with spring entrance
- Modal/sheet presentation → slide up with spring entrance
- Toggle switches → 200ms spring between on/off positions
- List row selection → brief highlight fade
- Section expansion → height + opacity transitions
- Section/card entrance → stagger entrance (translateY + opacity) with `--stagger-i` / `--row-i`
- Hero title/tagline/actions → cascade fade-in (0.15s delays)
- Feature cards on hover → **infinite bounce**: scale(1.05) + translateY(0→-5px), 1s ease-in-out infinite
- Forge glow → pulse: scale(0.9→1.1), 3s infinite alternate
- Forge icon → bob: translateY(0→-4px), 4s ease-in-out infinite
- Ember particles → float upward: translateY(0→-280px) + scale(1→0.2) + fade, 2.8-5s infinite

### Reduced Motion
When `prefers-reduced-motion: reduce` is active, ALL transitions and animations are disabled globally via `transition: none !important; animation: none !important;`. Additionally, hero-specific animations (glow, icon, embers, text fade-ins, card hover bounce) are explicitly reset to static state (opacity: 1, transform: none). State changes become instant. No information is lost — motion was never carrying semantic content.

### Reduced Transparency
When `prefers-reduced-transparency: reduce` is active, all `backdrop-filter` glass effects are replaced with solid `--surface` backgrounds. The nav bar loses the blur but maintains the scrim color.

**Intentional exemption**: The global ambient radial gradient on `.app-main` and the floating ambient particles are CSS `radial-gradient` and positioned elements (not `backdrop-filter`), so they are deliberately unaffected by this preference. These effects create visual atmosphere and carry no functional content — no information is lost if a user has reduced-transparency enabled.

## Do's and Don'ts

- **Do** use the system blue accent for interactive elements only. One interactive accent per viewport section maximum.
- **Do** use orange/yellow as forge decorative colors on the hero page — they are brand accents there, not warnings.
- **Do** use `ui-monospace` for all data display — token values, tensor scalars, loss numbers, code blocks, step counts.
- **Do** use the spacing grid strictly. Prefer using named variables (`var(--space-*)`) over raw values.
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
- **Don't** add drop shadows to nav bars — use glass instead.
- **Don't** use `@font-face` to embed SF Pro.
- **Don't** apply `backdrop-filter` to more than 3 simultaneous surfaces.
- **Don't** create new bespoke page layouts. Every page must fit into one of the five archetypes.
- **Don't** suppress reduced-motion or reduced-transparency preferences.
- **Don't** use forge glow or hero ember particles outside Archetype E — those are hero-exclusive effects. (Note: the global ambient particles in `base.html` are present on all pages, not hero-only.)