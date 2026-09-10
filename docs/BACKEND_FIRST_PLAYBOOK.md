# Backend-First Web Chat Provider Playbook

## Decision

For all Web Chat providers in this program, the preferred transport order is:

1. direct backend HTTP/SSE/WebSocket;
2. browser-context fetch/XHR using an authenticated browser session;
3. browser network interception/capture;
4. DOM submit/read fallback.

DOM is not the default inference transport unless the backend contract cannot yet be reproduced reliably.

## Discovery workflow

### 1. Establish a clean browser baseline

Use the normal logged-in web application. Record:

- target origin;
- current page URL;
- browser version and profile;
- account/session state;
- model/mode selected;
- whether search/thinking/tools are enabled.

Do not begin by copying every header. First identify which requests actually create/resume a conversation and which one carries the generated response.

### 2. Capture the backend graph

For one minimal prompt, identify in order:

- session/account validation;
- model/catalog request;
- conversation create/resume;
- anti-bot / challenge / PoW call;
- completion request;
- stream transport and framing;
- stop/cancel endpoint;
- cleanup/delete endpoint;
- upload/file lifecycle if present.

Store request method, path, content type, body schema, response schema and correlation IDs separately from sensitive credential values.

### 3. Classify session dependencies

Determine which of the following are actually required:

- Bearer token;
- cookies;
- XSRF token;
- localStorage/sessionStorage value;
- browser-generated request ID;
- Origin/Referer;
- browser client hints;
- fingerprint/TLS/JA3 coupling;
- IP/proxy affinity;
- anti-bot clearance;
- PoW/challenge response;
- volatile application build/version identifier.

Treat coupled fields as one versioned session/fingerprint bundle rather than independent strings.

### 4. Reproduce the smallest safe backend call

Prefer a low-risk read-only endpoint first, such as user info or model listing. Then test conversation creation and a deterministic completion.

A backend path is considered reproduced only when the minimum required headers/state are understood well enough that unnecessary browser headers can be removed without breaking it.

### 5. Implement stream parsing as a state machine

At minimum track:

`CONNECTING -> HEADERS -> WAIT_FIRST_EVENT -> STREAMING -> TERMINAL | FAILED | CANCELLED`

Use separate deadlines for:

- connection/headers;
- first parsed event;
- idle interval after meaningful events begin;
- total request lifetime.

Do not reset idle timeout for arbitrary bytes if they do not parse into meaningful stream events.

Detect errors embedded in an HTTP 200 stream.

### 6. Preserve the commitment boundary

Before upstream submit is confirmed, bounded retry may be safe.

After submit may have reached the provider, automatic replay is unsafe unless the provider explicitly proves rejection/non-acceptance. Otherwise return an ambiguous/transport failure and let the caller decide.

### 7. Normalize provider output above transport

Provider transport should emit a provider-neutral event stream such as:

- response started;
- reasoning delta;
- text delta;
- tool-call candidate;
- citation/source event;
- usage;
- terminal status;
- provider error.

OpenAI Chat Completions, Responses API, Anthropic or other outward protocols should be rendered above this layer.

## Tool-call normalization

Tool-call dialect parsing is a shared gateway concern.

Required pipeline:

1. hold ambiguous prefix while a stream could still become a known tool marker;
2. canonicalize full-width/zero-width/corrupted markup;
3. detect known dialect;
4. require the function name to exist in the request's declared tools;
5. parse balanced JSON safely;
6. validate/coerce argument schema;
7. reject missing required arguments;
8. de-duplicate equivalent calls;
9. bound parser memory;
10. if dialect is detected but unparseable, treat the turn as protocol failure rather than successful prose.

The gateway must support multiple dialect families because model failover or provider changes can continue a previous model's syntax.

## Browser-context backend fallback

If host-side HTTP fails because the web session is browser-bound, use browser-context `fetch()` before DOM automation.

This preserves:

- same-origin cookies;
- browser session storage;
- browser networking/fingerprint context;

while still using the backend protocol instead of manipulating the chat UI.

This mode must still apply origin/path restrictions before injecting any gateway-owned credential.

## Network interception fallback

If the request cannot yet be reproduced, instrument the authenticated browser to capture request/response metadata and stream payloads.

Use interception as a discovery mechanism and temporary transport, not as an excuse to leave the backend contract undocumented.

## DOM fallback

DOM is acceptable for:

- login/bootstrap;
- challenge completion where no stable backend method is available;
- model/UI state selection not yet mapped to backend flags;
- final inference fallback.

DOM transport must use:

- request-scoped state;
- page/session leases;
- explicit submission confirmation;
- crash/close invalidation;
- bounded queues/backpressure metrics;
- robust completion detection;
- no automatic replay after commitment.

## Capability truthfulness

Every provider/transport should advertise at least:

- canonical model IDs;
- chat completion support;
- tool support;
- vision/file support;
- search/thinking modes if meaningful;
- streaming support;
- `streaming_mode`: `native`, `captured`, `buffered`, or `none`;
- session requirements;
- backend transport currently selected;
- fallback transports available.

Never advertise a model alias or capability that the currently active session/transport has not proved.

## Security rules

- bind local development gateways to loopback unless exposure is deliberate;
- keep runtime secrets outside tracked config;
- normalize and validate origin/path before credential injection;
- never match credential destinations by naive string prefix;
- redact tokens/cookies/session IDs from logs;
- truncate/redact upstream error bodies;
- maintain a version for fingerprint/challenge state;
- invalidate anti-bot/session artifacts when fingerprint or proxy/IP changes;
- fail closed on unknown provider, model, origin or tool name.

## Provider-specific starting points

### DeepSeek Web

Use the independently verified direct backend flow already developed in the DeepSeek project: session creation, PoW challenge, completion SSE and tool normalization.

### Qwen Web

Start with the source-inspected flow from qwen2API:

- `GET /api/v2/user/info` for token validation;
- `GET /api/models` for catalog discovery;
- `POST /api/v2/chats/new`;
- `POST /api/v2/chat/completions?chat_id=...` with SSE;
- cleanup via `/api/v2/chats/<id>`;
- direct HTTP first, browser-context fetch fallback if session/fingerprint binding requires it.

### ChatGPT Web

Current DOM provider remains operational as fallback. Next research target is the authenticated backend conversation request/stream. Do not replace the working DOM path until a backend transport passes independent E2 tests.

### Z.ai Web

Begin with browser network capture and enumerate session/model/conversation/stream calls. Reproduce a read-only account/model endpoint first, then deterministic completion. DOM remains fallback until the backend path is independently verified.

## Acceptance gates for a new backend transport

A provider transport is not `operational` until all applicable gates pass:

- auth/session validation;
- canonical model listing;
- deterministic non-stream completion;
- native/captured stream reconstruction;
- first-event and idle timeout tests;
- upstream error-in-200 test;
- cancellation/stop behavior;
- tool-call normalization;
- full tool round-trip;
- unknown model/provider fail-closed;
- credential/log redaction checks;
- restart/reconnect behavior;
- repeated live runs with recorded latency/error metrics.

Only after repeated predefined live metrics over independent windows should the transport be called E3.
