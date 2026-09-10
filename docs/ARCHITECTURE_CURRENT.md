# Hooshka Web Gateway — Current Architecture

## Purpose

Hooshka Web Gateway isolates Web-chat integration complexity from Hooshka and other clients. Provider-specific UI, frontend modules, sessions, signatures, anti-abuse state and transport quirks must not leak into the Hooshka orchestration layer.

```text
Hooshka / Kilo / local SDK / local agent
                  |
                  v
        OpenAI-compatible local API
                  |
          request normalization
                  |
                  v
        exact fail-closed router
          /        |        \
         /         |         \
chatgpt-web     qwen-web     zai-web
    |              |            |
 provider-local transport + runtime/session ownership
                  |
            normalized response
```

DeepSeek remains a registered research/workstream concept but is not an enabled live provider while the current account state is blocked.

## Layers

### 1. API layer

Primary endpoints:

- `GET /health`
- `GET /ready`
- `GET /health/deep`
- `GET /modes`
- `GET /v1/models`
- `POST /v1/chat/completions`
- additional compatibility endpoints already present in `main.py`

The API layer validates and normalizes request shapes. It must not contain provider-specific browser logic.

### 2. Canonical request model

`ChatCompletionRequest` carries normalized messages and provider options such as:

- `model`
- `messages`
- `temperature`
- `top_p`
- `max_tokens`
- `stream`
- `tools`
- `tool_choice`
- `conversation_id`
- `thinking`
- `search`
- `file_paths`
- `upstream_model`

Provider support for these options is capability-gated. Unsupported options must fail explicitly.

### 3. Provider registry/router

Canonical model ids are exact routing keys:

- `chatgpt-web`
- `qwen-web`
- `zai-web`

No substring matching, guessed aliases, or cross-provider fallback is permitted.

### 4. Provider adapters

Each provider implements a common contract:

- `health_check()`
- `list_models()`
- `chat_completion()`
- `chat_completion_stream()`
- `close()`

Each adapter owns provider-specific capability truth and transport provenance.

### 5. Transport strategy

Preferred order:

1. direct provider backend HTTP/SSE/WebSocket when safe and reproducible;
2. browser-context fetch or provider frontend controller;
3. network/controller capture;
4. DOM interaction only when no safer backend-oriented path is available.

Backend-first does not mean bypassing provider controls. Provider-owned CAPTCHA/session/signature flows remain provider-owned.

### 6. Commitment-aware retry boundary

Every provider interaction conceptually moves through:

```text
not_sent -> maybe_sent -> committed -> terminal
```

Retry is allowed only while the system can prove the upstream request was not committed. Once submission may have happened, automatic replay is forbidden because it can duplicate user turns.

### 7. Stream state

The shared conceptual stream lifecycle is:

```text
CONNECTING
HEADERS_RECEIVED
WAITING_FIRST_EVENT
STREAMING
TOOL_AMBIGUOUS
COMPLETED | FAILED | CANCELLED
```

Timeouts should distinguish connection/header timeout, first meaningful event timeout, meaningful idle timeout, and total timeout.

## Runtime ownership

- ChatGPT Web: existing CDP/browser context; ordinary user tabs are not assumed bridge-owned.
- Qwen Web: dedicated runtime/profile under `.runtime\qwen-profile`.
- Z.ai Web: dedicated CDP runtime/profile under `.runtime\zai-profile`, port 9223.
- Owned runtime labels use `HWG-`.

Cleanup must use explicit owned profile paths, never URL-only matching.

## Security boundaries

- loopback API
- bearer authentication
- runtime secrets outside Git
- exact provider routing
- fail-closed unsupported features
- sanitized evidence/logging
- no CAPTCHA/WAF/suspension bypass
- no unapproved sensitive organizational data through unofficial Web providers

## Evidence taxonomy

- **E0:** source/docs/research
- **E1:** deterministic unit/synthetic/prototype evidence
- **E2:** real Web-chat end-to-end evidence
- **E3:** repeated predefined reliability evidence across independent windows

Current release is an E2 baseline, not E3.
