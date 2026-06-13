# Feature Specification: Systemic Frontend Refactor — microGPT Learning Tool

**Feature Branch**: `004-frontend-refactor`
**Created**: 2026-06-12
**Status**: Draft
**Input**: User description: Systemic frontend refactoring across a multi-page site — layout, design, UX, information architecture, and component primitives for an interactive ML learning tool.

## User Scenarios & Testing

### User Story 1 — Live Training Dashboard (Priority: P1)

A practitioner opens the training page, configures hyperparameters (embedding size, layer depth, learning rate, steps), and starts a training run. The page establishes a live connection to the engine and streams real-time metrics as the model trains. A loss curve builds incrementally on a chart, and the current step, loss value, and throughput are displayed. Connection states (connecting, streaming, done, errored, reconnecting) are visually distinct. The practitioner can stop or resume training at any point.

**Why this priority**: This is the hero experience — the core emotional payload of the product. Watching a real loss curve tick because `train()` is actually stepping is the primary differentiator vs. static tutorials. Everything else supports or surrounds this experience.

**Independent Test**: Can be tested end-to-end by starting a training run and observing live loss updates across all connection state transitions. Delivers immediate value: users can train a real GPT model and watch it learn.

**Acceptance Scenarios**:

1. **Given** a user on the training page with default hyperparameters, **When** they click "Start Training", **Then** a live loss curve begins plotting and step/loss/throughput values update in real time
2. **Given** an active training run, **When** the user clicks "Stop", **Then** the stream halts, the connection state updates to "done", and the final loss curve is preserved
3. **Given** a network interruption during training, **When** the connection drops, **Then** the UI transitions to a "reconnecting" state with distinct visual treatment, and resumes seamlessly when the connection is restored
4. **Given** a completed training run of 10,000 steps, **When** the user returns to the page, **Then** the rendered loss curve does not degrade performance (DOM remains responsive, chart does not freeze)

---

### User Story 2 — Scroll-Driven Concept Explorer (Priority: P1)

A learner navigates to a concept page (e.g., "What is an Attention Head?"). The page presents a sticky visualization pane alongside a scrolling column of narrative steps. As the learner scrolls, each step entering the viewport drives the pinned visualization to update its state — highlighting attention patterns, showing token relationships, or animating forward-pass data flow. Interactive widgets (text input for tokenization, sliders for temperature/top-k, hoverable heatmaps for attention) respond to direct manipulation beyond scrolling.

**Why this priority**: This realizes the core product vision — "explorable explanation" in the lineage of Distill.pub. Without this, the site is just documentation with screenshots. The attention page receives the most layout allocation as the centerpiece of the learning arc.

**Independent Test**: Can be tested by navigating to any concept page, scrolling through narrative steps, and confirming the pinned visualization updates state correctly at each step. Widgets respond to direct input (typing, clicking, sliding). Delivers immediate value: a self-contained interactive lesson.

**Acceptance Scenarios**:

1. **Given** a learner on the Attention concept page, **When** they scroll down through narrative steps, **Then** the pinned attention heatmap updates to highlight tokens attended to by each head
2. **Given** a tokenization widget, **When** the learner types text into the input, **Then** the widget shows the live token/ID split updating character by character
3. **Given** a sampling widget with temperature/top-k sliders, **When** the learner adjusts a slider, **Then** the next-token probability distribution re-rolls in real time
4. **Given** a concept page on a mobile device, **When** scrolling, **Then** the pinned visualization collapses inline, stacked with its corresponding step text rather than stuck off-screen

---

### User Story 3 — Experiment History & Replay (Priority: P2)

A practitioner browses past training runs from the experiment history page. The page lists all runs with status indicators (completed, failed, in-progress). Selecting a run opens a detail view showing the run's configuration, final metrics, and — critically — a replay of its loss curve using the same chart component as the live training page. A run is addressable by URL for sharing with colleagues.

**Why this priority**: Supports the primary training workflow by allowing comparison and review. Reuses the live chart primitive, so no second chart implementation is needed. Enables collaboration through shareable URLs.

**Independent Test**: Can be tested by completing a training run, navigating to the experiment list, selecting the run, and confirming the replayed loss curve matches what was shown live. Delivers independent value: persistent record of experiments.

**Acceptance Scenarios**:

1. **Given** a completed training run, **When** the practitioner navigates to the experiment history page, **Then** the run appears in the list with a "completed" status indicator
2. **Given** a selected run on the detail page, **When** the page loads, **Then** the full final loss curve is rendered immediately using the same chart visual style as the live training page (no step-by-step animation)
3. **Given** a run detail page with a shareable URL, **When** the URL is shared and opened by another user, **Then** the same run detail is displayed

---

### User Story 4 — Computation Graph Exploration (Priority: P2)

A curious learner examines how a forward pass works by viewing the actual computation graph built by the autograd engine. The view shows real nodes and operations (not a hand-drawn diagram), with mono type for values and real op labels. The learner can scrub through the forward pass to watch the graph assemble step by step into a prediction. When the graph is large, the view degrades gracefully (projection/level-of-detail) rather than freezing.

**Why this priority**: This is the "legibility jackpot" — the clearest expression of the "no magic" brand ethos. Exposing real engine structure builds credibility that no static diagram can match.

**Independent Test**: Can be tested by loading the graph view page, scrubbing through forward-pass steps, and confirming each step adds the correct operations with real labels. Delivers independent value: a unique pedagogical tool.

**Acceptance Scenarios**:

1. **Given** a loaded computation graph view, **When** the learner scrubs through forward-pass steps, **Then** operations are added to the graph in the correct order
2. **Given** any node in the graph, **When** the learner inspects it, **Then** the node displays its real op type and value in mono typeface
3. **Given** a large model configuration producing many graph nodes, **When** the view loads, **Then** it renders without freezing (projection or level-of-detail activates automatically)

---

### User Story 5 — Theme, Navigation & Cross-Page State (Priority: P3)

A user explores multiple concept pages in sequence. The navigation bar reflects the learning arc order and indicates their current location. When they switch between pages — or between light and dark mode via a persistent toggle — their active-run identity, theme preference, and model configuration survive navigation. Shareable URLs encode run ID and config for sharing.

**Why this priority**: Essential for coherence but lower risk than the interactive surfaces. Without this, the experience feels disjointed and unpolished. With it, the site feels like a single integrated learning tool rather than disconnected pages.

**Independent Test**: Can be tested by navigating between pages and confirming the theme preference persists, the nav highlights the current page, and a URL with query params restores the correct state on direct load.

**Acceptance Scenarios**:

1. **Given** a user who toggles dark mode, **When** they navigate to a different page and reload, **Then** dark mode persists
2. **Given** a URL containing a run ID, **When** loaded directly, **Then** the page displays that run's context without the user needing to re-select it
3. **Given** a user on a concept page, **When** they check the navigation bar, **Then** the current page is highlighted and the nav order follows the learning arc (Tokenization → Embeddings → Attention → Forward Pass → Sampling → Training Loop → Payoff)

---

### Edge Cases

- What happens when SSE connection drops mid-training? Stream should attempt reconnect with capped exponential backoff (up to 5 retries: 1s, 2s, 4s, 8s, 16s) with visual feedback. After exhausting retries, transition to permanent "errored" state with a manual "Retry" button.
- What happens when a 10,000+ step training run returns a massive dataset? Chart data must be downsampled for display without losing the shape of the curve.
- What happens on a mobile device with a pinned/sticky visualization? The layout collapses to inline stacking so both text and visual remain accessible.
- What happens when `prefers-reduced-motion` is active? All animated transitions become instant but state changes still occur.
- What happens when a concept page has fewer or more steps than expected? The `ScrollScene` primitive should handle any number of steps without breaking layout.
- What happens when the user navigates away during an active training run? The EventSource must be closed on unmount/navigation to prevent orphan connections.
- What happens when an interactive widget receives keyboard focus? Every widget must be fully keyboard-operable with visible focus indicators.
- What happens when the experiment history page has zero runs? The page shows a contextual placeholder ("No runs yet — train your first model") with a clear call-to-action to start a training session, not a bare empty list.
- What happens when a concept page loads before any step is scrolled into view? The page shows a "Scroll to begin" prompt with the first step's pinned visual already rendered, giving the user immediate context.
- What happens when a run detail page loads while metrics are still being fetched from the database? The page shows a loading indicator in the chart area and status text ("Loading metrics…") — not a blank or broken chart.

## Clarifications

### Session 2026-06-12

- Q: How should experiment history and concept pages render in empty/loading states? → A: Show contextual placeholder content with guidance — "No runs yet" with CTA for experiment list, "Scroll to begin" with preview for concept pages, loading indicator for run detail metrics.
- Q: How many SSE reconnect retries before permanent error, and what backoff strategy? → A: Capped exponential backoff (5 retries: 1s, 2s, 4s, 8s, 16s), then permanent "errored" state with manual "Retry" button.
- Q: What quantified performance target for the live training page? → A: Perceived responsiveness — user can interact with controls within 100ms of input at any point, rather than a specific fps target.
- Q: Does the computation graph view require a new backend API endpoint? → A: Yes — a new lightweight endpoint exposing the autograd graph structure is in scope. The "no new backend APIs" assumption is updated accordingly.
- Q: Should the replay chart animate the curve building or render the final curve immediately? → A: Render the full final curve immediately on load, using the same chart component and visual style as the live page but populated from stored data (no step-by-step animation).

## Requirements

### Functional Requirements

- **FR-001**: The system MUST provide a single app shell that wraps all pages with a unified navigation reflecting the learning arc order.
- **FR-002**: Users MUST be able to start, monitor, and stop training runs from a live dashboard page that streams real-time metrics via a persistent connection.
- **FR-003**: The live dashboard MUST render all six connection states (idle, connecting, streaming, done, errored, reconnecting) with visually distinct treatment. Reconnection MUST use capped exponential backoff (up to 5 retries: 1s, 2s, 4s, 8s, 16s), followed by a permanent errored state with a manual "Retry" button.
- **FR-004**: The live chart MUST be append-only, rendered on a throttled cadence, and downsample display data past a configurable horizon to prevent unbounded DOM growth.
- **FR-005**: Concept pages MUST use a shared scroll-driven primitive (`ScrollScene`) with a pinned visualization pane that updates state as narrative steps enter the viewport.
- **FR-006**: The scroll-trigger mechanism MUST detect when narrative steps enter the viewport and clean up observation on unmount — no per-section scroll-offset calculations.
- **FR-007**: Interactive concept widgets MUST respond to direct manipulation (typing, clicking, dragging, sliding) and MUST be fully keyboard-operable.
- **FR-008**: The attention concept page MUST receive the largest layout allocation among concept pages.
- **FR-009**: Users MUST be able to browse past training runs, view run details, and replay metrics using the same chart component used for live training.
- **FR-010**: Runs and shareable configuration MUST be addressable via URL params that restore correctly on direct load.
- **FR-011**: A light/dark mode toggle MUST persist the user's choice across navigation and page reloads. Default follows the operating system preference.
- **FR-012**: All color, type, spacing, motion, and radius values MUST be defined as centralized design tokens. Components reference tokens only, never raw values.
- **FR-013**: All text/background color pairings MUST meet WCAG AA contrast requirements in both light and dark modes.
- **FR-014**: The computation graph view MUST be sourced from real engine data, not a static illustration. It must degrade gracefully when the graph is large.
- **FR-015**: All animated transitions MUST respect `prefers-reduced-motion`. Under reduced motion, state changes are instant.
- **FR-016**: Every sticky/pinned layout MUST have a defined inline-stacked collapse on mobile viewports.
- **FR-017**: The live data connection MUST be properly closed when the user navigates away from or closes the live training page.
- **FR-018**: The ANSI terminal theme (ANSI 16-color palette, all-mono chrome, phosphor/CRT/scanline treatment) MUST be fully removed and replaced by a proper editorial light/dark design.
- **FR-019**: Monospace typeface MUST be retained for code, tokens, tensor values, and weight rendering specifically — only the terminal theme is removed, not mono typography for data.
- **FR-020**: No global mutable singletons may hold state that a page refresh silently loses. State continuity is via URL params (shareable/durable) and browser session storage (ephemeral UI).

### Key Entities

- **Learning Arc**: The ordered sequence of concept pages (Tokenization, Embeddings, Attention, Forward Pass, Sampling, Training Loop, Payoff). Determines navigation order and content progression.
- **ScrollScene**: A reusable scroll-driven page template consisting of a pinned visualization pane and an ordered list of narrative Steps. Each Step entering the viewport emits a state key that drives the pinned visual.
- **Training Run**: A single training session with hyperparameters (n_embd, n_layer, n_head, num_steps, learning_rate, temperature), current status, streaming metrics (loss, step, throughput), and final results.
- **Design Token System**: A centralized set of named design values (color, type, spacing, motion, radius) defined per theme mode. All components reference these semantic tokens.
- **Connection State Machine**: The lifecycle states of the SSE stream: idle → connecting → streaming → done → errored → reconnecting. Each state has distinct visual treatment.
- **Concept Widget**: A manipulable interactive artifact within a concept page (tokenization input, embedding projection, attention heatmap, sampling slider, training loop visualizer).
- **App Shell**: The shared layout wrapper providing navigation, theme toggle, page frame, and cross-page state boundary for all archetypes.

## Success Criteria

### Measurable Outcomes

- **SC-001**: Learners can navigate the complete concept arc (7 stops) without getting lost or needing to use browser back/forward — navigation clearly indicates current location and next/previous content.
- **SC-002**: The live training page renders responsively under high-frequency SSE emission (emits faster than paint budget): user can interact with controls within 100ms of input at any point, no unbounded DOM growth (applies to all rendered elements — canvas, metrics display, status indicators) after 10,000 steps, chart remains interactive.
- **SC-003**: The ANSI terminal theme is fully removed across all pages and routes; light and dark modes both meet WCAG AA contrast ratios for all text/background pairings (verified by automated contrast checking).
- **SC-004**: All concept pages share exactly one `ScrollScene` primitive and one `useActiveStep` mechanism — adding a new concept page requires only adding Steps, not new scroll logic.
- **SC-005**: A completed training run is accessible via shareable URL that restores run context on direct load (no extra clicks or searches).
- **SC-006**: Every interactive widget (minimum 5: tokenization, embeddings, attention, sampling, training loop) is fully operable and visibly focusable via keyboard alone.
- **SC-007**: The live chart and replay chart use the same visual primitive — no visually distinct second chart implementation.
- **SC-008**: A systemic restyle (e.g., changing all accent colors) requires editing only token values, not individual component files.

## Assumptions

- **Stack decision (JS-app)**: The frontend is a lean JavaScript application consuming the FastAPI JSON + SSE API, not a Jinja-template-served app. Cross-page state lives in URL params + a minimal client store. This assumption was documented in the feature description and is carried forward.
- **Computation Graph View**: The computation graph view (§4.4 of the feature description) is in scope for this refactor and will be built as part of the concept page migration. It is not a post-refactor aspiration.
- **Existing route mapping**: Every existing route MUST be retrofitted into one of the four archetypes:
  - `/v1/training-page`, `/v1/` → Archetype B (live training dashboard)
  - `/v1/experiments-page` → Archetype C (run history)
  - `/v1/inference-page` → Archetype D (playground/sandbox)
  - `/v1/datasets-page` → Archetype B-adjacent (reuse training layout, replace SSE content with dataset management content)
  - `/v1/operations-page` → Archetype B-adjacent (reuse training layout, replace SSE content with service control content)
  - `/v1/models-page`, `/v1/model-detail/{id}` → Archetype C-adjacent (reuse experiment list/detail layout, replace with model registry content)
  - `/learn/*` → Archetype A (concept pages)
  No per-route bespoke layouts remain after migration.
- **No new backend APIs (updated)**: The frontend refactor may restructure API consumption. A new lightweight endpoint exposing the autograd computation graph structure is in scope (needed for FR-014). All other existing functionality must reuse existing endpoints.
- **No new JS dependencies**: New JavaScript dependencies require explicit justification against the dependency-lean ethos. Default is to use platform primitives (IntersectionObserver, EventSource, CSS custom properties, native canvas/SVG).
- **All existing pages are retrofitted**: Every existing page/route must be retrofitted into one of the four archetypes (concept, live training, run history, playground). No per-route bespoke layouts remain after migration.