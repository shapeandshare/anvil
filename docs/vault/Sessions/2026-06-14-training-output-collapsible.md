## Summary
Made the training Output section collapsible with a live status indicator dot. The Output section on the training page (`/v1/training-page`) previously showed a full-height log panel with no way to collapse it and no visual cue for whether a training process was actively producing output.

Added: clickable header (section-card__header becomes a toggle), a green indicator dot with three visual states (idle/gray, active/pulsing green glow, done/solid green), and a rotating chevron. The collapsible body wraps both the `<pre>.loss-display` log panel and the output actions bar (register model, view experiments, MLflow link).

## Files changed
- `anvil/api/templates/archetypes/training.html` — Output section header now `role="button"` with `aria-expanded`/`aria-controls`; new `.output-indicator` and `.output-toggle-icon` spans in header; output body wrapped in `#output-body.section-card__content-collapsible`; JS additions: element refs, `updateOutputIndicator(state)`, `toggleOutput()`, content tracking via `_outputHasContent`, hooked into `updateState()` and `log()`; reset logic in `startTraining()`
- `anvil/api/static/css/archetypes.css` — New style blocks for: `.section-card__content-collapsible` (overflow hidden, max-height transition), `.section-card__header--clickable` (cursor/hover), `.output-indicator--idle/--active/--done` (three dot states with pulse keyframe), `.output-toggle-icon.collapsed` (chevron rotation)

## Key decisions
- Indicator uses three states: idle (dim), active (pulsing green glow), done (solid green) — matching the existing `connection-state` pattern (`cs-idle`, `cs-streaming`, `cs-done`)
- Collapse uses `max-height` transition rather than `display: none` / `height: auto` — simpler animation, sufficient for the bounded log panel
- Output actions (register model, etc.) live inside the collapsible — they're semantically part of the output section and hiding them together avoids layout confusion
- Keyboard accessible: Enter/Space to toggle, `aria-expanded` attribute tracks state
- Indicator only turns `--active` when BOTH a streaming process is running AND `_outputHasContent` is true — avoids false "green means active" when a session connects but hasn't logged anything yet
