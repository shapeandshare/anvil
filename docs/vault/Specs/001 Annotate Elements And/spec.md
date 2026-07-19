---
title: "001 Visual Feedback Annotation"
type: spec
tags:
  - type/spec
  - domain/ui
spec-refs:
  - docs/vault/Specs/001 Annotate Elements And/
created: 2026-07-18
updated: 2026-07-18
spec_number: 001
status: draft
doc_type: spec
epic: "User Experience"
aliases:
  - 001 Visual Feedback Annotation
---

# Feature Specification: Visual Feedback Annotation

**Spec status:** ✅ ready for planning
**Feature Branch**: `001-annotate-elements-and`  
**Created**: 2026-07-18  
**Input**: User description: "i want a user to be able to annotate elements that dont work and leave notes about the experience. they should also be able to circle an area and leave te notes"

## Clarifications

### Session 2026-07-18

- Q: How should the viewport screenshot be captured? → A: Client-side DOM-based capture (e.g., html2canvas) — captures the rendered DOM in the browser, no server round-trip.
- Q: How long should feedback reports be retained? → A: Manual deletion only — no auto-cleanup; admins delete reports when done.
- Q: What drawing tools should be available beyond circles? → A: Element click, circles, and freehand drawing — circles for precise areas, freehand for arbitrary shapes.
- Q: Should admins be able to export feedback reports? → A: Full report export (JSON + annotated screenshot) — reports must be machine-readable so automated agents can consume the information to fix bugs.
- Q: How should error states (capture failure, empty submission, network error) be handled? → A: Toast notifications — non-blocking messages that allow users to retry without losing context.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Annotate a Broken Element (Priority: P1)

A user notices a UI element that isn't working (e.g., a button that doesn't respond, a chart that doesn't load). They enter annotation mode, click on the element to mark it, and leave a note describing the issue.

**Why this priority**: This is the core functionality — marking specific UI elements that are broken is the primary use case.

**Independent Test**: Can be fully tested by entering annotation mode, clicking on any visible UI element, attaching a text note, and submitting — confirming the annotation is saved and retrievable.

**Acceptance Scenarios**:

1. **Given** the user is viewing any page in the app, **When** they activate annotation mode and click on a UI element, **Then** the element is visually highlighted and a note input field appears
2. **Given** the user has clicked on an element to annotate it, **When** they type a description of the issue and confirm, **Then** the annotation is saved and a visual marker appears on the element
3. **Given** the user has annotated one or more elements, **When** they submit the feedback report, **Then** all annotations are packaged together and delivered

---

### User Story 2 - Circle an Area and Leave Notes (Priority: P1)

A user wants to draw attention to a region of the screen (e.g., a section with misaligned content, a missing panel, or a visual glitch that spans multiple elements). They use a circle tool to highlight the area and add a note.

**Why this priority**: Circling arbitrary regions is the second core capability — it covers issues that aren't tied to a single interactive element.

**Independent Test**: Can be fully tested by entering annotation mode, drawing a circle on the page, attaching a note, and submitting — confirming the circle annotation is saved.

**Acceptance Scenarios**:

1. **Given** the user is in annotation mode, **When** they select the circle tool and draw a circle on the page, **Then** the circle is rendered as a visible overlay with a note input field attached
2. **Given** the user has drawn a circle, **When** they type a note and confirm, **Then** the circled annotation is saved with its position, size, and note
3. **Given** the user has multiple annotations (element clicks and circles), **When** they review them before submitting, **Then** each annotation is visible and editable

---

### User Story 3 - Review Submitted Feedback (Priority: P2)

An administrator or developer reviews feedback submissions to see what users have reported — including which elements were marked, what circles were drawn, and what notes were left.

**Why this priority**: The feedback is only useful if someone can act on it. This story makes the annotation feature valuable by closing the loop.

**Independent Test**: Can be fully tested by submitting a feedback report with annotations, then navigating to a feedback review page and verifying the report appears with all annotations intact.

**Acceptance Scenarios**:

1. **Given** a feedback report has been submitted, **When** an admin views the feedback dashboard, **Then** the report appears in a list with timestamp, page URL, and annotation count
2. **Given** an admin opens a submitted feedback report, **When** they view the report details, **Then** they see a screenshot of the page with all annotations (element markers and circles) overlaid at their original positions, along with the associated notes
3. **Given** an admin reviews a feedback report, **When** they mark it as resolved or add a response, **Then** the status is updated and visible to the original reporter

---

### Edge Cases

- What happens when the user annotates an element that is part of a dynamic UI (e.g., a dropdown that closes when clicked)? The annotation mode should capture a screenshot of the page at the moment the user enters annotation mode, so annotations are placed on a static snapshot.
- How does the system handle page scrolling when annotations are placed? Circles and element markers should be positioned relative to the viewport at the time of capture, since the feedback is anchored to a screenshot.
- What happens if the user navigates away while in annotation mode? The system should warn the user that unsaved annotations will be lost.
- How does the system handle very long notes? Notes should have a reasonable character limit (e.g., 2000 characters) with a visible counter.
- What happens if the user tries to annotate a page element that is hidden or off-screen? The annotation mode should capture the current viewport only — users can scroll to capture different areas of the page.
- How are old reports cleaned up? Reports are manually deleted by administrators — no automatic retention policy. The feedback dashboard should support bulk selection and deletion of reports.
- What if the viewport screenshot capture fails? A non-blocking toast notification should inform the user and offer a retry option without disrupting their annotations.
- What if the user tries to submit with no annotations? A toast notification should warn that the report is empty and confirm they want to submit it anyway.
- What if the submission fails due to a network error? A toast notification should inform the user and allow them to retry submission. Annotations should be preserved in the browser until successfully submitted.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Users MUST be able to enter and exit an annotation mode from any page in the app via a persistent toggle (e.g., a floating button).
- **FR-002**: When annotation mode is activated, the system MUST capture a screenshot of the current viewport to serve as the annotation canvas.
- **FR-003**: Users MUST be able to click on any visible UI element within the captured viewport to mark it as an annotation target.
- **FR-004**: For each clicked element, users MUST be able to attach a free-text note describing the issue.
- **FR-005**: Users MUST be able to draw circles (free-form ovals) and freehand strokes on the viewport screenshot to highlight arbitrary areas.
- **FR-006**: For each circled area, users MUST be able to attach a free-text note.
- **FR-007**: Users MUST be able to review, edit, and delete their annotations (both element markers and circles) before submission.
- **FR-008**: Users MUST be able to submit all annotations as a single feedback report.
- **FR-009**: Each submitted feedback report MUST include: the page URL, a timestamp, the viewport screenshot with all annotations overlaid, and the text of each note.
- **FR-010**: Submitted feedback reports MUST be persisted via the app database and file storage, and accessible via an in-app feedback dashboard within the existing admin/operations interface, viewable by users with administrative privileges.
- **FR-011**: Administrators MUST be able to view submitted feedback reports, see all annotations on the screenshot, read notes, and update the report status (e.g., open, in progress, resolved).
- **FR-012**: The system MUST warn users before they navigate away or close the tab while unsaved annotations exist.
- **FR-013**: Notes MUST have a maximum length of 2000 characters.
- **FR-014**: Administrators MUST be able to delete individual feedback reports, with confirmation, from the feedback dashboard.
- **FR-015**: The feedback dashboard MUST support bulk selection and deletion of multiple feedback reports at once.
- **FR-016**: Administrators MUST be able to export individual feedback reports as a structured machine-readable format (JSON with all metadata, annotations, notes, and page URL) plus the annotated screenshot image.
- **FR-017**: The export format MUST include sufficient structure (coordinates, element selectors, note text, annotation types) for automated agents to parse and act on the feedback.

### Key Entities

- **Feedback Report**: A collection of annotations submitted by a user at a single point in time. Contains: page URL, timestamp, viewport screenshot, reporter identity, status.
- **Element Annotation**: A marker tied to a specific UI element position. Contains: element coordinates/selector, note text, type (element marker).
- **Drawing Annotation**: A free-form shape (circle or freehand stroke) drawn on the viewport. Contains: shape coordinates/path data, note text, type (circle or freehand).
- **Feedback Reviewer**: An administrator or developer who views and acts on submitted feedback reports.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Users can complete the full annotation flow (enter annotation mode → mark elements/draw circles → add notes → submit) in under 2 minutes on first use.
- **SC-002**: Submitted feedback reports preserve all annotation positions and notes with pixel-level accuracy relative to the captured viewport.
- **SC-003**: Administrators can view any submitted report and immediately understand which elements or areas were flagged and what the issue was, without needing to contact the reporter.
- **SC-004**: The annotation workflow operates without degrading the performance of the page being annotated (annotation mode is lightweight and non-blocking).

## Related

- [[Systems/Systems|Systems]] — this spec modifies the web UI layer
- [[Specs/Specs|Specs]] — folder MOC

## Assumptions

- Users have a modern web browser with screenshot capture and overlay capabilities.
- The annotation feature is for surfacing usability issues and broken UI elements, not for general-purpose image annotation.
- Feedback reports are consumed by the app's development or support team — not by end users.
- Users will not need to annotate content that spans multiple pages or requires cross-page navigation.
- The annotation tool captures only the current viewport (visible area), not the full page height.
- Screenshot capture uses client-side DOM-based rendering (e.g., html2canvas) — consistent with industry-standard in-browser annotation tools.
- The existing authentication system will be reused — only logged-in users can submit feedback.
- Mobile/responsive layout feedback is supported as long as the viewport capture works correctly at any screen size.