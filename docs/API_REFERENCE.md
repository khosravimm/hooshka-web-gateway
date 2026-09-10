# Hooshka Web Gateway — API Reference

Base URL:

```text
http://127.0.0.1:5000
```

The service is intentionally loopback-only.

## Authentication

Most operational endpoints are governed by bearer authentication.

```http
Authorization: Bearer <runtime-key>
```

The runtime key is sourced from local runtime configuration/service environment. Never hard-code it in source or documentation.

## GET /health

Lightweight process identity/liveness.

Example response:

```json
{
  "status": "ok",
  "service": "hooshka-web-gateway",
  "legacy_service": "mcp-web-bridge"
}
```

Use this to determine whether the HTTP process is alive. Do not treat it as proof that every upstream provider is usable.

## GET /ready

Provider readiness view.

Observed 0.5.0 shape:

```json
{
  "status": "ready",
  "providers": [
    {"provider": "zai-web", "ready": true},
    {"provider": "qwen-web", "ready": true},
    {"provider": "chatgpt-web", "ready": true}
  ]
}
```

Use `/ready` before dispatching provider work.

## GET /health/deep

Deeper provider/runtime health endpoint. It may be slower or exercise provider runtime checks. Use it for diagnostics, not as a high-frequency liveness probe.

## GET /modes

Returns provider capabilities/provenance. Clients should use this endpoint rather than assuming every provider supports tools, search, files, vision or native streaming.

Important capability fields include:

- `chat_completion`
- `streaming`
- `streaming_mode`
- `tools`
- `vision`
- `embeddings`
- `search`
- `reasoning`
- `files`
- `transport_mode`

## GET /v1/models

Returns canonical aliases plus provider-discovered routable models.

Current naming policy:

- `chatgpt-web` — canonical ChatGPT Web model id;
- `qwen-web` — configurable Qwen default model;
- `qwen:<upstream-id>` — exact Qwen model discovered from the active provider catalog;
- `zai-web` — configurable Z.ai default model;
- `zai:<upstream-id>` — exact Z.ai model discovered from the active provider catalog.

Current tracked defaults are:

```text
qwen-web -> qwen3.8-max
zai-web  -> glm-5.3
```

The list is dynamic: newly advertised upstream ids may appear without a gateway code change. Namespaced models are validated against the current provider/session catalog before submit.

## POST /v1/chat/completions

OpenAI-compatible primary endpoint.

Minimal request:

```json
{
  "model": "qwen-web",
  "messages": [
    {"role": "user", "content": "Explain TLS 1.3 briefly."}
  ]
}
```

Typical non-stream response:

```json
{
  "id": "chatcmpl-...",
  "object": "chat.completion",
  "model": "qwen-web",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": "...",
        "tool_calls": null
      },
      "finish_reason": "stop"
    }
  ],
  "usage": {
    "prompt_tokens": 0,
    "completion_tokens": 0,
    "total_tokens": 0
  },
  "provider_meta": {
    "provider_id": "qwen-web",
    "transport_mode": "browser_backend_controller",
    "streaming_mode": "reconstructed"
  }
}
```

Token usage can be unavailable/zero for Web transports and must not be treated as authoritative billing telemetry.

### Streaming

Set:

```json
"stream": true
```

The HTTP response is `text/event-stream` with OpenAI-style data frames and terminal:

```text
data: [DONE]
```

Streaming provenance is provider-specific. `reconstructed` or `buffered` is not equivalent to a native upstream token stream.

### Provider-specific options

The request normalizer currently recognizes options including:

```json
{
  "thinking": true,
  "search": false,
  "upstream_model": null,
  "file_paths": [],
  "long_text": true
}
```

A recognized option is not automatically supported by every provider. Check `/modes`.

### Tools

Tools are currently accepted only where the provider capability advertises `tools=true`. The established ChatGPT Web path supports normalized tool calls; Qwen and Z.ai tools remain disabled until independent E2 tool-roundtrip acceptance.

Never assume an empty tool allow-list means wildcard access.

## Routing rules

- Explicit canonical model wins.
- Unknown model: error.
- Unsupported capability: error.
- Provider unavailable: error.
- No hidden substitution to another provider.

## Error contract

Errors use a normalized envelope similar to:

```json
{
  "error": {
    "message": "Provider unavailable",
    "type": "provider_unavailable",
    "provider": "zai-web",
    "details": {}
  }
}
```

Consumers should branch on `error.type`/provider state rather than parsing human-readable text.

## Client guidance

For Hooshka, use:

1. `/health` for process health;
2. `/ready` for provider readiness;
3. `/modes` for feature negotiation;
4. `/v1/models` for routing choices;
5. `/v1/chat/completions` for execution.

Do not import provider adapter classes from Hooshka.
