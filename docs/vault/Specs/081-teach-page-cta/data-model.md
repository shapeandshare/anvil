# Data Model: Teach Page Workflow State Machine

**Phase**: Phase 1 — Design & Contracts  
**Date**: 2026-07-03  
**Status**: Complete

## Overview

The teach page's behavioral logic is a client-side state machine driving which panels are visible and which CTAs are shown. No server-side data changes are involved — the state machine operates on the existing API responses.

## Workflow States

```text
┌──────────────────────────────────────────────────────────┐
│                     Page Load                            │
│                                                          │
│   sessions.length === 0         sessions.length > 0      │
│         │                              │                 │
│         ▼                              ▼                 │
│   ┌──────────┐                 ┌──────────────┐          │
│   │ EMPTY    │                 │ SESSION_LIST │          │
│   │ STATE    │                 │ (no active)  │          │
│   └────┬─────┘                 └──────┬───────┘          │
│        │                               │                 │
│        │  user clicks                  │ user clicks     │
│        │  "Create Session"             │ a session       │
│        └──────────┬────────────────────┘                 │
│                   ▼                                      │
│            ┌──────────────┐                              │
│            │ SESSION      │                              │
│            │ ACTIVE       │                              │
│            │ (idle)       │                              │
│            └──────┬───────┘                              │
│                   │                                      │
│         ┌─────────┴─────────┐                            │
│         ▼                   ▼                            │
│   ┌──────────┐       ┌──────────────┐                    │
│   │ ROUND    │       │ ROUNDS_EXIST │                    │
│   │ RUNNING  │       │ (1+ rounds)  │                    │
│   └────┬─────┘       └──────┬───────┘                    │
│        │                    │                            │
│        ▼                    ▼                            │
│   ┌──────────┐       ┌──────────────┐                    │
│   │ ROUND    │       │ COMPARE_     │                    │
│   │ COMPLETE │       │ READY        │                    │
│   └────┬─────┘       │ (≥2 rounds)  │                    │
│        │             └──────────────┘                    │
│        ▼                                                 │
│   ┌──────────┐                                           │
│   │ INSPECT  │                                           │
│   │ READY    │                                           │
│   └──────────┘                                           │
└──────────────────────────────────────────────────────────┘
```

## State Definitions

### EMPTY_STATE
- **Trigger**: Page loads with `data.sessions.length === 0` (or initial state before session list response)
- **Behavior**: Show guidance card in main content area; hide all panels (round, inspect, compare); sidebar shows "No sessions yet" text
- **Exit**: User creates a session → SESSION_ACTIVE

### SESSION_LIST (no active selection)
- **Trigger**: Sessions exist but none selected
- **Behavior**: Guidance card still visible; panels hidden; sidebar shows session list
- **Exit**: User clicks a session → SESSION_ACTIVE

### SESSION_ACTIVE (idle)
- **Trigger**: User selects a session (or creates one)
- **Behavior**: Active session panel visible with "Start New Round" CTA; round panel visible; inspect panel hidden; rounds count checked for COMPARE_READY
- **Exit**: User clicks "Start New Round" → ROUND_RUNNING; or clicks another session → back to SESSION_ACTIVE for that session

### ROUND_RUNNING
- **Trigger**: `startRound()` POST succeeds, SSE connection opens
- **Behavior**: Training progress bar visible; "Start New Round" button disabled; active session shows running status
- **Exit**: SSE `complete` event → ROUND_COMPLETE; SSE `error` event → SESSION_ACTIVE (with error state)

### ROUND_COMPLETE
- **Trigger**: SSE `complete` event fires
- **Behavior**: Post-training CTA button ("Inspect This Round →") appears in active panel/completion section; re-enable "Start New Round"; check rounds count for COMPARE_READY
- **Exit**: User clicks "Inspect This Round →" → INSPECT_READY; or clicks "Start New Round" → ROUND_RUNNING

### INSPECT_READY
- **Trigger**: User clicks post-training CTA
- **Behavior**: Inspect panel appears with experiment ID pre-filled from completed round; user can enter prompt and click "Generate"
- **Exit**: User can still start another round or compare

### COMPARE_READY
- **Trigger**: `loadSessionDetails()` or round completion detects ≥2 completed rounds
- **Behavior**: Compare panel becomes visible (was hidden via JS)
- **Exit**: Not a terminal state — coexists with SESSION_ACTIVE

## Client-Side State Variables

The existing JS variables at `teach.html` line 195-198 are retained. One addition needed:

| Variable | Current | Change |
|----------|---------|--------|
| `activeSessionId` | ✅ Exists (line 195) | No change |
| `activeRunId` | ✅ Exists (line 196) | No change |
| `activeMlflowRunId` | ✅ Exists (line 197) | No change |
| `activeEventSource` | ✅ Exists (line 198) | No change |
| `completedRounds` | ❌ New | Needed to track rounds count for COMPARE_READY state |

## Validation Rules

- Guidance card must hide when sessions exist AND one is selected
- Post-training CTA must only appear for the round that just completed (not retroactively)
- Compare panel visibility is gated on `completedRounds >= 2`
- "Inspect This Round" must pre-fill the experiment ID from the completed run, not from user input
- Empty state card should not reappear during normal session switching (only when session list becomes empty)