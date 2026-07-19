# Data Model: In-Memory Chat Structures

## Overview

Chat conversations are ephemeral for v1 — stored only in the browser's JavaScript memory. No SQLite tables, no Alembic migrations, no server-side persistence. This keeps the feature simple (Article XI) and avoids new database dependencies.

## Entities

### ChatConversation

An in-memory session holding a sequence of user/assistant turns. Lives only in the browser's JavaScript VM.

```javascript
{
  id: string,          // UUID v4, generated on page load
  modelRef: string,    // model name (e.g., "demo" or modelKey)
  modelVersion: number, // 1 by default
  temperature: number,  // 0.5 default
  messages: ChatMessage[],
  createdAt: timestamp,
  activeStream: null | ChatStream,
}
```

### ChatMessage

A single turn in the conversation.

```javascript
{
  role: "user" | "assistant",
  text: string,
  timestamp: timestamp,
  status: "complete" | "streaming" | "cancelled" | "interrupted",
}
```

### ChatStream

Represents an in-progress generation.

```javascript
{
  // Managed by the client-side SSESession
  sessionId: string,
  state: "streaming" | "completed" | "cancelled" | "errored",
  partialText: string,
}
```

## State Transitions

```
ChatMessage.status:
  "streaming" ──(complete)──→ "complete"
  "streaming" ──(cancel)────→ "cancelled"
  "streaming" ──(interrupt)─→ "interrupted"

ChatStream.state:
  "streaming" ──(complete event)──→ "completed"
  "streaming" ──(user click)──────→ "cancelled"
  "streaming" ──(error event)─────→ "errored"
```

## Context Window Management

When building the prompt for the model, the client assembles the conversation history into a single string:

```
User: {message 1}
Assistant: {response 1}
User: {message 2}
Assistant: {response 2}
...
```

This string is sent to the generation endpoint. If the concatenated prompt exceeds the model's `block_size` (context length), the oldest `User: ... Assistant: ...` pairs are dropped (from the client-side, before sending) until the prompt fits within the limit. A subtle progress indicator near the model selector shows context usage.

## Export Format

Downloaded conversation uses plain text with role labels:

```
Conversation — 2026-07-19

─── User ───
message text here

─── Assistant ───
response text here

─── User ───
...
```