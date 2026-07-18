# Feature Specification: Teach Page Onboarding & CTA Remediation

**Feature Branch**: `062-teach-page-cta`  
**Created**: 2026-07-03  
**Status**: Draft  
**Input**: User description: "the teach page has no call to action and is unusable, critically review and provide a remediation plan"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - First visit: empty state guidance (Priority: P1)

A user navigates to the Teaching Loop page for the first time. They have no existing sessions and have never used the feature before. The page should immediately communicate what the Teaching Loop does and what the first step is, rather than presenting a blank main content area.

**Why this priority**: This is the default state — every user sees this on first visit. Without guidance, users will not understand the Teaching Loop concept or how to start, making the entire feature undiscoverable.

**Independent Test**: A new user can land on the page, read the guidance, and successfully create their first session without leaving the page or consulting external help.

**Acceptance Scenarios**:

1. **Given** a user navigates to the Teaching Loop page with no sessions, **When** the page loads, **Then** the main content area displays a centered guidance card with an icon, a welcome message explaining the Teaching Loop concept, a numbered step list (Create Session → Train Round → Inspect Results), and a prominent "Create Session" button.
2. **Given** a user sees the empty-state guidance card, **When** they click the "Create Session" button in the card, **Then** the session is created and the page transitions to the active session state.
3. **Given** a user has created one or more sessions, **When** they return to the page, **Then** the empty-state guidance card is replaced with the session list and active panels.

---

### User Story 2 - Active session: flow continuity (Priority: P1)

A user has selected an active session. The page should show what's happening now, what they can do next, and provide clear action buttons at each stage of the workflow.

**Why this priority**: The current page hides the round workflow and inspect panels behind `display:none`, and provides no "next step" after training completes. This creates a dead-end user experience where users must guess what to do next.

**Independent Test**: A user with an active session can complete a full cycle (start a round → watch training → see completion → inspect results) using only on-screen CTAs, without guessing which hidden panel to open next.

**Acceptance Scenarios**:

1. **Given** a user has an active session with no running round, **When** they view the active session panel, **Then** they see a "Start New Round" primary CTA button alongside session info and status.
2. **Given** a training round completes, **When** the SSE stream signals completion, **Then** a post-training CTA button appears (e.g., "Inspect This Round →") that auto-fills the Inspect panel with the completed round's experiment ID.
3. **Given** a user completes training, **When** the Inspect panel becomes active, **Then** the experiment ID is pre-filled from the completed round and the user only needs to enter a prompt and click "Generate".
4. **Given** a user wants to start another round, **When** they are in the active session panel, **Then** a "Start New Round" button is always available.

---

### User Story 3 - Progressive disclosure of panels (Priority: P2)

The page progressively reveals panels and controls as the user advances through the teaching workflow, rather than showing irrelevant or unusable controls from the start.

**Why this priority**: The Compare panel is always visible on page load but requires at least 2 experiment IDs to function. This clutters the interface with dead controls and confuses new users.

**Independent Test**: A user sees only the controls relevant to their current stage — Compare is hidden (or shows placeholder guidance) until at least 2 rounds exist.

**Acceptance Scenarios**:

1. **Given** a user has fewer than 2 completed rounds, **When** the page loads, **Then** the Compare panel is either hidden or displays placeholder text explaining the user needs to complete at least 2 rounds first.
2. **Given** a user has 2 or more completed rounds, **When** they view the page, **Then** the Compare panel is displayed with the experiment ID fields ready for input.
3. **Given** a user has no active session selected, **When** they view the main content area, **Then** only guidance/empty state is shown — no partial form controls from hidden panels are visible.

---

### User Story 4 - Educational context and cross-references (Priority: P3)

The Teaching Loop is the most complex concept in the application. The page provides educational cross-references, orientation, and entrance animations consistent with the rest of the application's design language.

**Why this priority**: The playground, learn-index, and other pages include learning-lesson CTAs, a "Did You Know?" banner, and staggered entrance animations. The teach page lacks all of these, making it feel disconnected from the rest of the app.

**Independent Test**: A user sees a "Did You Know?" banner on the teach page and can follow a link to a related learning lesson about iterative training.

**Acceptance Scenarios**:

1. **Given** a user scrolls to the bottom of the teach page, **When** the page renders, **Then** a "Did You Know?" banner is visible with educational content related to the Teaching Loop.
2. **Given** a user sees the banner, **When** they click the dismiss button, **Then** the banner is hidden for the session.
3. **Given** a user loads the page, **When** section cards appear, **Then** they animate in with staggered entrance timing (using `--stagger-i`) consistent with other pages in the application.

---

### Edge Cases

- What happens when a user has many sessions (20+) — does the sidebar scroll properly without cluttering?
- How does the page behave when training fails mid-round? Does the user get a clear error state with a retry affordance?
- What happens when the user deletes the currently active session mid-workflow?
- How does the page handle the case where the active session has 0 rounds — does it show a "start your first round" prompt?
- Does the empty-state guidance disappear appropriately when returning from a session to the empty list (e.g., after deleting the only session)?

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The page MUST display a centered guidance card in the main content area when no teaching session is active, containing: a welcome message explaining the Teaching Loop concept, a numbered step list (Create → Train → Inspect), and a "Create Session" button.
- **FR-002**: The "Create Session" button in the guidance card MUST create a new session (same behavior as the sidebar form) and transition the page to the active session state.
- **FR-003**: The active session panel MUST include action buttons: "Start New Round" (primary CTA) and optionally "Delete Session" (with confirmation) and "View Rounds".
- **FR-004**: When a training round completes via SSE, a post-training CTA MUST appear (e.g., "Inspect This Round" button) that opens the Inspect panel with the completed round's experiment ID pre-filled.
- **FR-005**: The Inspect panel MUST auto-reveal and pre-fill the experiment ID from the most recently completed round when the post-training CTA is triggered.
- **FR-006**: The Compare panel MUST be hidden (or display placeholder guidance) until at least 2 completed rounds exist in the active session.
- **FR-007**: The page MUST include a "Did You Know?" banner consistent with the pattern used on the playground and learn-index pages.
- **FR-008**: Section cards on the teach page MUST use staggered entrance animation consistent with the application's design system, using `--stagger-i` custom properties.
- **FR-009**: The sidebar "Create Session" button MUST be visually distinct as the primary entry point for new users.

### Key Entities *(include if feature involves data)*

- **Teaching Session**: A named container that holds a chain of training rounds. Has status, name, description, and chain head tracking the current base experiment. Created by the user and listed in the sidebar.
- **Training Round**: A single training run within a session. Has examples, hyperparameters, an experiment ID (MLflow), and training status. Created when the user starts a round.
- **Round Workflow State**: The user's current position in the teaching loop — either "no session", "session active / no rounds", "round running", "round complete / ready to inspect", or "rounds completed / ready to compare".

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A first-time user can create their first teaching session and start a training round using only on-screen guidance and CTAs, without leaving the page or consulting external documentation.
- **SC-002**: After a training round completes, the user can reach the inspect panel in 1 click (the post-training CTA) rather than the current experience of discovering a hidden panel and manually entering the experiment ID.
- **SC-003**: The dead initial state (blank main content area) is eliminated entirely — every load state of the page displays meaningful content and a clear next action.
- **SC-004**: The Compare panel is never shown in an unusable state — it is either hidden or carries placeholder guidance when fewer than 2 rounds exist.
- **SC-005**: The visual presentation of the teach page matches the consistency of the playground and learn-index pages, as measured by the presence of staggered entrance animations, a "Did You Know?" banner, and educational cross-reference CTAs.

## Assumptions

- The user is already familiar with the general concept of ML training (from other pages in the app) but may be unfamiliar with the iterative Teaching Loop workflow.
- The existing backend API (teach routes, SSE streaming, inspect, compare) is complete and functional — this spec covers only the frontend UX layer.
- The "Did You Know?" banner pattern from `base.html` block `didyouknow_banner` is the standard pattern to follow.
- Staggered entrance animations follow the existing `--stagger-i` pattern used throughout the application's archetype templates.
- The empty-state guidance card should be dismissible for returning users who already understand the workflow.
- The post-training CTA should only appear for the most recently completed round (not for historical rounds viewed after page reload).
