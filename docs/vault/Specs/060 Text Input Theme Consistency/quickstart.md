# Quickstart: Text Input Theme Consistency

**Date**: 2026-06-29  
**Plan**: [plan.md](plan.md) | **Spec**: [spec.md](spec.md) | **Research**: [research.md](research.md)

## What This Is

A pure CSS refactor to unify all text-editing inputs across the app. No new dependencies, no backend changes, no database migrations.

## Implementation Order

### 1. Fix the core `.form-input` class (components.css)

| Change | From | To |
|--------|------|----|
| Add border | `border: none` | `border: 1px solid var(--separator)` |
| Fix radius | `border-radius: var(--radius)` (13px) | `border-radius: var(--radius-sm)` (8px) |
| Add touch target | _(none)_ | `min-height: var(--touch-min)` (44px) |
| Focus ring | `:focus` | `:focus-visible` (keep `:focus` as fallback) |
| Disabled state | _(none)_ | `.form-input:disabled { opacity: 0.4; ... }` |
| Readonly state | _(none)_ | `.form-input[readonly] { background: var(--surface); }` |

### 2. Consolidate `.terminal-input` → `.form-input`

`.terminal-input` shares the same CSS block as `.form-input` (components.css lines 44-51). Combine selectors:

```css
/* Before */
.terminal-input, .form-input, .form-select { ... }

/* After — remove .terminal-input, keep .form-input and .form-select */
.form-input, .form-select { ... }
```

### 3. Align `.widget-input` tokens

`.widget-input` (components.css line 190) should keep its mono font and width behavior but adopt the same border, radius, and focus tokens:

```css
.widget-input {
  background: var(--surface-2);
  border: 1px solid var(--separator);      /* added */
  border-radius: var(--radius-sm);         /* was var(--radius) */
  /* keep: font-family: var(--font-mono), width: 100%, etc. */
}
.widget-input:focus-visible {               /* was :focus */
  box-shadow: 0 0 0 2px var(--accent);
}
```

### 4. Migrate login page (login.html + login.css)

In `login.html` line 24: change `class="login-card__input"` → `class="form-input"`.

In `login.css`: remove the `.login-card__input` rule block (lines 72-91). The `.form-input` class covers all visual properties. Login layout classes (`.login-card`, `.login-card__field`, `.login-card__label`) stay.

### 5. Fix config modal orphan (config.html)

Line 307: change `class="input"` → `class="form-input"`.

### 6. Fix training param bare inputs (training.html)

Lines 116, 122, 128, 135, 142, 148, 154: add `class="form-input"` to each `<input type="number">`.

In `archetypes.css`: simplify the `.param-block input` rule (line 25-26) to remove duplicate input styling — let `.form-input` handle it, keep only `.param-block` layout styles:

```css
/* Before */
.param-block input {
  width: 100%; padding: var(--space-2) var(--space-3);
  background: var(--surface); border: none; border-radius: var(--radius-sm);
  color: var(--text); ... 
}

/* After — remove redundant visual properties, keep width */
.param-block input {
  width: 100%;
}
```

### 7. Update compute backend `<select>` (training.html)

Line 161: remove inline `style` attributes for visual properties (background, border, color, font-size, border-radius). Apply `class="form-input"` instead. Keep only layout properties (width: 100%) if needed.

### 8. Run verification

```bash
make ux-lint        # S4 gate — must pass
make lint           # ruff + black + isort
# Visual: manually check inputs on:
#   - Home page
#   - Training page (7 param inputs + compute backend select)
#   - Datasets page (search, create, wizard inputs)
#   - Config page (modal edit input)
#   - Login page
#   - Playground page (prompt, temperature, samples)
#   - HF Browser (search)
#   - Concept widgets (tokenization, etc.)
#   - Toggle dark/light mode on each
#   - Activate 3+ behavioral themes
```

## Files to Modify

| File | Change |
|------|--------|
| `anvil/api/static/css/components.css` | Core `.form-input` class rewrite |
| `anvil/api/static/css/archetypes.css` | Simplify `.param-block input` |
| `anvil/api/static/css/login.css` | Remove `.login-card__input` block |
| `anvil/api/templates/login.html` | Class swap: `login-card__input` → `form-input` |
| `anvil/api/templates/config.html` | Class swap: `"input"` → `"form-input"` |
| `anvil/api/templates/archetypes/training.html` | Add `form-input` class to 7 inputs + fix select |
| `anvil/api/templates/partials/concept-widgets/tokenization.html` | Verify `widget-input` still works |

## Key Decisions

- **Focus**: `:focus-visible` with `:focus` fallback
- **Border**: `1px solid var(--separator)`
- **Radius**: `var(--radius-sm)` = 8px
- **Widgets**: Keep `.widget-input` as separate class, align tokens
- **Themes**: No theme-level changes needed — base token inheritance covers all 23 themes