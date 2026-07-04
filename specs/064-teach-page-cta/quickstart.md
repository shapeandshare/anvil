# Quickstart: Teach Page UX Remediation

## Testing the Changes

### Prerequisites

```bash
make setup   # ensure venv + deps
make run     # start web server + MLflow
```

Open `http://localhost:8080/v1/teach` in a browser.

### Test Scenarios

**1. Empty State (FR-001, FR-002)**

1. Navigate to `/v1/teach` with no existing sessions
2. **Expected**: Main content area shows a centered guidance card with an icon, "Welcome to the Teaching Loop" message, numbered steps (Create → Train → Inspect), and a "Create Session" button
3. Click the "Create Session" button in the guidance card
4. **Expected**: Session is created, main area transitions to active session state with panel visible

**2. Active Session CTAs (FR-003, FR-009)**

1. Select an existing session from the sidebar
2. **Expected**: Active session panel shows "Start New Round" button; sidebar "Create Session" button is visually distinct

**3. Post-Training Flow (FR-004, FR-005)**

1. Select a session, enter examples in the round form, click "Start Round"
2. **Expected**: Training progress bar appears
3. Wait for training to complete
4. **Expected**: A button appears (e.g., "Inspect This Round →"); clicking it reveals the Inspect panel with the experiment ID pre-filled from the completed round

**4. Progressive Disclosure (FR-006)**

1. With fewer than 2 completed rounds:
   **Expected**: Compare panel is hidden (or shows placeholder "Complete 2 rounds to compare")
2. After completing 2+ rounds:
   **Expected**: Compare panel becomes visible with experiment ID fields

**5. Visual Polish (FR-007, FR-008)**

1. Load the page
2. **Expected**: Section cards animate in with staggered timing (`--stagger-i`)
3. Scroll to bottom
4. **Expected**: "Did You Know?" banner visible

### UX Gate Verification

```bash
make ux-lint   # deterministic S4 gate — must pass
```

Then run the AI UX review (if UX_API_KEY configured):

```bash
make ux-review
```

The gate should report `GATE: PASS` since all S3 findings from the initial review are resolved.

### Browser Test (Optional)

```bash
make test-browser   # Playwright smoke tests (if e2e tests for teach page exist)
```