# Chat Streaming API Contract

## GET /v1/chat/stream

Starts a new chat generation session and streams the model's response character-by-character via SSE.

### Query Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `model_name` | string | no | demo model | Name of the model to chat with |
| `model_version` | int | no | latest | Model version number |
| `temperature` | float | no | `0.7` | Sampling temperature (0.1–2.0) |
| `prompt` | string | yes | — | The user's message text |

### SSE Event Stream

#### Event: `chunk`

Sent for each newly generated character.

```
event: chunk
data: {"text": "t"}
```

A complete response streams one `chunk` event per character. The client appends each character to the current assistant message.

#### Event: `complete`

Sent when generation finishes normally.

```
event: complete
data: {"text": "", "tokens_generated": 42}
```

The client marks the assistant message as `complete`.

#### Event: `error`

Sent when generation fails.

```
event: error
data: {"message": "Generation failed: model not found"}
```

The client displays the error message and marks the message as `errored`.

#### Event: `heartbeat`

Sent every 30 seconds to keep the connection alive during long generations (matching existing SSE pattern).

```
event: heartbeat
data: {}
```

### Example Client-Side Usage

```javascript
var es = new EventSource('/v1/chat/stream?prompt=Hello&temperature=0.5');
var msg = '';
es.addEventListener('chunk', function(e) {
  var d = JSON.parse(e.data);
  msg += d.text;
  appendToChatOutput(d.text);
});
es.addEventListener('complete', function(e) {
  es.close();
  finalizeMessage(msg);
});
es.addEventListener('error', function(e) {
  es.close();
  showError('Generation failed');
});
```

### Response Headers

```
Content-Type: text/event-stream
Cache-Control: no-cache
X-Accel-Buffering: no
```

### Error Responses

| Status | When |
|--------|------|
| 400 | Missing `prompt` parameter |
| 404 | Model not found or not loadable |
| 422 | Invalid temperature value |
| 500 | Generation engine error |