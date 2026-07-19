---
title: "001 Inference Chat Split"
type: spec
tags:
  - type/spec
  - domain/api
  - domain/ui
spec-refs: []
created: 2026-07-19
updated: 2026-07-19
spec_number: 001
status: draft
doc_type: spec
epic: "Inference & Chat UX"
aliases:
  - 001 Inference Chat Split
---

# Feature Specification: Play &rarr; Inference (Rename) + New Chat Page

**Spec status:** &#9203; waiting  
**Feature Branch**: `001-inference-chat-split`  
**Created**: 2026-07-19  
**Input**: User description: "Play page needs to become 'Inference' (renamed, same UX) + a new Chat page with conversational UI, streaming, model selector, and conversation history"

## User Scenarios & Testing

### User Story 1 &mdash; Rename "Play" to "Inference" (Priority: P1)

As a user, I want the navigation label "Play" to be renamed to "Inference" so that the page's name matches its actual function &mdash; running model inference/sampling.

**Why this priority**: This is a trivial rename with no UX impact; it's a terminology correction. Doing it first clears the deck for the new Chat page and avoids confusion between "Play" and "Chat" in the nav.

**Independent Test**: Can be verified by checking the navigation bar displays "Inference" instead of "Play" for the `/v1/inference-page` route. No other functionality changes.

**Acceptance Scenarios**:

1. **Given** a user visits any page in the app, **When** they look at the navigation bar, **Then** the tab linking to `/v1/inference-page` displays the label "Inference" instead of "Play"
2. **Given** the existing inference/sampling playground at `/v1/inference-page`, **When** a user navigates to it, **Then** the page renders exactly as before &mdash; same layout, controls, and behavior &mdash; with only the nav label changed

---

### User Story 2 &mdash; Chat with a Model (Priority: P1)

As a user, I want to send a message to a loaded model and see its response stream back character-by-character, so that I can interact with the model conversationally rather than in batch mode.

**Why this priority**: This is the core value of the Chat page. Everything else (model selection, conversation history) is secondary to being able to have a conversational interaction.

**Independent Test**: Can be tested by selecting a model, typing a message, clicking send, and watching the response stream in. No conversation persistence needed.

**Acceptance Scenarios**:

1. **Given** a model is loaded and the chat page is open, **When** the user types a message and clicks Send, **Then** the model's response appears in the chat output, streaming character-by-character as it is generated
2. **Given** the user is viewing a completed response, **When** they send a follow-up message, **Then** both messages appear in the conversation history as a multi-turn thread
3. **Given** the demo model failed to provision and no models are available, **When** the user attempts to send a message, **Then** they see a clear message indicating no models are available and the send button is disabled
4. **Given** the demo model is available, **When** a user visits the chat page for the first time, **Then** the demo model is pre-selected so they can start chatting immediately

---

### User Story 3 &mdash; Model Selector in Chat (Priority: P2)

As a user, I want to choose which model to chat with from a dropdown, so that I can switch between models without leaving the chat page.

**Why this priority**: Model selection powers the chat experience but can be pre-populated with a default (demo model). Users need this to use their trained or imported models.

**Independent Test**: Can be tested by verifying the model dropdown populates with available models and selecting a different model changes which model responds to messages.

**Acceptance Scenarios**:

1. **Given** the chat page is open, **When** the page loads, **Then** the model selector shows available models populated from the inference model list
2. **Given** a model is selected and a conversation is in progress, **When** the user switches to a different model, **Then** subsequent messages use the new model (previous conversation history is preserved for reference)
3. **Given** the user has multiple model versions, **When** they select a model with multiple versions, **Then** they can also select which version to use

---

### User Story 4 &mdash; Export a Conversation (Priority: P3)

As a user, I want to save or export my chat conversation before leaving the page, so that I can keep a record of the model's responses even though conversations are ephemeral.

**Why this priority**: Conversations are in-memory only and lost on page refresh. An export button gives users a way to preserve interesting outputs without requiring full persistence infrastructure.

**Independent Test**: Can be tested by having a conversation, clicking the export option, and verifying the output contains the full message history in a readable format.

**Acceptance Scenarios**:

1. **Given** the user has had a chat conversation with at least one exchange, **When** they click the export button, **Then** the full conversation (all user and assistant messages in order) is available for download or clipboard copy
2. **Given** the user refreshes the page, **When** the chat page reloads, **Then** the conversation is cleared (ephemeral by design) and a fresh empty chat starts

---

### Edge Cases

- **No models available**: When no demo model exists and no trained models are registered, the chat page renders with a clear message and disabled send button. Users are directed to train a model first.
- **Long message input**: Messages exceeding the 2000-character limit are rejected at the UI level with a visible warning before sending.
- **Streaming interruption**: If the connection drops mid-stream, partial output is preserved in the conversation history with a "cancelled" or "interrupted" marker so the user can retry.
- **Context overflow**: When the conversation history exceeds the model's context window, oldest messages are silently truncated. A subtle context usage indicator (e.g., a progress bar near the model selector) shows how much of the model's context is consumed.
- **Cancelled generation**: If the user clicks the cancel button, the partial output is preserved in the conversation history with a "cancelled" marker so the user can review what was generated.
- **Degraded mode (MLflow unavailable)**: The chat page continues to function using cached/available models — model loading from MLflow may fail, but the page degrades gracefully without crashing.

## Requirements

### Functional Requirements

- **FR-001**: Navigation tab for `/v1/inference-page` MUST display "Inference" instead of "Play"
- **FR-002**: The existing inference/sampling playground page MUST remain functionally unchanged &mdash; no modifications to its layout, controls, or behavior
- **FR-003**: Users MUST be able to send a text message and receive a model-generated response
- **FR-004**: Model responses MUST stream character-by-character as they are generated
- **FR-005**: Users MUST be able to select which model to chat with from a dropdown populated with available models
- **FR-006**: When the demo model is available, it MUST be pre-selected as the default chat model so the user can start immediately
- **FR-007**: Multi-turn conversation MUST be supported &mdash; follow-up messages appear in the same conversation thread
- **FR-008**: Users MUST be able to configure the generation temperature (via a slider control with range 0.1–2.0) from within the chat UI
- **FR-009**: The chat page MUST gracefully handle the case where no models are available (clear message, disabled send button)
- **FR-010**: Users MUST be able to stop/cancel an in-progress generation
- **FR-011**: The chat page MUST be navigable from the main navigation bar (new "Chat" tab)
- **FR-012**: Existing navigation smoke tests, e2e page render tests, and any browser tests MUST be updated to cover the new Chat page and the renamed Inference nav label
- **FR-013**: The demo model auto-provisioning system MUST work with the chat streaming endpoint (same as it does with the sampling endpoint)
- **FR-014**: Chat messages MUST have a character limit of 2000 characters to prevent abuse or accidental excessive generation; exceeding this limit MUST show a visible warning before the message is sent
- **FR-015**: Users MUST be able to export or copy the current conversation as plain text with role labels ("User"/"Assistant")
- **FR-016**: When the conversation history exceeds the model's context window, the oldest messages MUST be silently truncated to make room for new input
- **FR-017**: A subtle UI indicator (e.g., a progress bar near the model selector) MUST show how much of the model's context window is consumed

### Key Entities

- **ChatConversation**: A sequence of user and assistant messages within a single chat session. Stored in-memory in the browser, with a unique identifier, model reference, messages list, and timestamp.
- **ChatMessage**: A single turn in a conversation &mdash; either from the user (prompt) or the assistant (response). Contains the message text, role (user/assistant), and timestamp.
- **ChatStream**: An in-progress generation that is actively streaming output to the user. Has a state (streaming, completed, cancelled, errored) and can be cancelled by the user.

## Success Criteria

### Measurable Outcomes

- **SC-001**: A user can send a message and see the first characters of the response begin streaming within 1 second (for the demo model)
- **SC-002**: Multi-turn conversations of at least 10 back-and-forth exchanges work without degradation or state corruption
- **SC-003**: The navigation rename requires zero user re-education &mdash; the label change is self-explanatory
- **SC-004**: The chat page renders successfully on first load (demo model pre-selected) without requiring the user to configure anything
- **SC-005**: All existing tests pass (regression), and new tests cover the chat page render, streaming interaction, model selection, and navigation

## Related

- [[Systems/Systems|Systems]] &mdash; the inference service and demo model provider
- [[Specs/Specs|Specs]] &mdash; folder MOC

## Assumptions

- Chat conversations are ephemeral for v1 &mdash; they are not saved permanently and are lost when the user leaves the page
- The demo model is automatically available on first visit &mdash; no additional setup steps are needed for the chat page to work out of the box
- Temperature is the primary generation control exposed in the chat UI; additional parameters can be added in future iterations
- The chat page is a new navigation entry alongside the renamed "Inference" page &mdash; it replaces no existing page
- The user typically has at least one model available to chat with; the case where no models exist is handled as an edge case (informative message, disabled input)
- When the conversation history exceeds the model's context window, the oldest messages are silently truncated to make room for new input, with a subtle UI indicator showing context usage

## Clarifications

### Session 2026-07-19

- Q: How should the chat page handle context window overflow when conversation history exceeds the model's context length? → A: Silently truncate oldest messages with a subtle UI indicator showing context usage.