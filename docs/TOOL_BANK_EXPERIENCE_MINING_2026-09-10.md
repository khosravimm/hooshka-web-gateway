# D:\Tools Experience Mining — 2026-09-10

## Mission

Research and extract reusable engineering knowledge from the local `D:\Tools` bank for the unified Web Chat API program. The target architecture is a single OpenAI-compatible gateway over ChatGPT Web, DeepSeek Web, Qwen Web, and Z.ai Web.

This report distinguishes source inspection from runtime proof. Static/source findings below are implementation evidence from the inspected projects, not proof that the upstream site behavior still works today. Any transferred behavior must be re-tested independently in `mcp-web-bridge` before being treated as E2.

## Corpus

- 89 top-level folders in `D:\Tools`
- 87 local Git repositories
- 80 unique GitHub repositories after de-duplicating repeated local clones/remotes
- Live GitHub metadata collected for all 80 unique repositories
- Release-asset download counts collected for 60 priority repositories
- Deep source inspection performed on the backend-heavy / Web-to-API candidates listed below

Research artifacts in `D:\Tools`:

- `_inventory.json`
- `_github_meta.json`
- `_release_downloads.json`
- `_endpoint_inventory.json`

## Primary source-inspected projects

### `YuJunZhiXue/qwen2API` — `D:\Tools\048-qwen2api`

Source-inspected backend contract:

- Base origin: `https://chat.qwen.ai`
- Create chat: `POST /api/v2/chats/new`
- Completion stream: `POST /api/v2/chat/completions?chat_id=<id>`
- Chat detail/delete/list: `/api/v2/chats/...`
- Model catalog: `GET /api/models`
- User/token validation: `GET /api/v2/user/info`
- Vision task status: `GET /api/v1/tasks/status/<id>`
- File operations include `/api/v2/files/getstsToken`, `/api/v2/files/parse`, and `/api/v2/files/parse/status`

Important implementation lessons:

1. **Backend-first is practical for Qwen.** The project uses direct HTTP against Qwen's web backend rather than depending on DOM for normal inference.
2. **Browser-shaped headers matter.** Requests carry Origin, Referer, User-Agent, sec-ch-ua, sec-fetch-* and a generated `x-request-id` in addition to Bearer authorization.
3. **Chat creation and completion are separate lifecycle steps.** A stateless OpenAI request maps onto a temporary upstream chat session that should be deleted after use unless explicit conversation continuity is requested.
4. **Streaming needs phase-specific timeouts.** The client distinguishes response-header timeout, first parsed SSE event timeout, and idle timeout after streaming begins. A single total timeout is not enough.
5. **Only meaningful events reset idle timeout.** Mere bytes are insufficient; parsed content/reasoning events reset the idle deadline.
6. **Upstream errors can arrive inside HTTP 200 streams.** The stream parser explicitly detects upstream error objects embedded in SSE payloads.
7. **Tool calling is a normalization problem, not a single syntax.** Qwen2API supports QNML/XML/JSON/text-KV tool-call forms, validates against the declared tool schema, coerces argument types, rejects missing required arguments, de-duplicates repeated calls, then renders either Chat Completions `tool_calls` or Responses API `function_call` items.
8. **Corrupted markup is expected.** The QNML parser canonicalizes full-width pipes, zero-width characters, malformed tag glyphs, missing parameter closes, CDATA boundaries and other damaged markup before parsing.
9. **Thinking and tools may conflict at the upstream layer.** The payload builder disables upstream thinking automatically when custom tool handling is in use unless explicitly overridden. This is a provider-specific capability interaction that should be represented in the capability contract.
10. **Request correlation is first-class.** An upstream request ID is generated and propagated into logs and error messages.

Transfer status for `mcp-web-bridge`:

- Backend-first Qwen provider: **adopt**
- First-event + idle timeout split: **adopt**
- Error-inside-200-stream detection: **adopt**
- Canonicalization before tool parsing: **already partially adopted; extend from this design**
- Tool-schema validation/coercion/deduplication: **adopt**
- Temporary upstream chat lifecycle: **adopt**

### `NIyueeE/ds-free-api` — `D:\Tools\073-ds-free-api`

Source-inspected DeepSeek web backend:

- Base: `https://chat.deepseek.com/api/v0`
- `/users/login`
- `/chat_session/create`
- `/chat/create_pow_challenge`
- `/chat/completion`
- `/chat/edit_message`
- `/chat/stop_stream`
- `/chat_session/delete`
- `/chat_session/update_title`
- `/file/upload_file`
- `/file/fetch_files`

Important implementation lessons:

1. **PoW is a separate protocol subsystem.** The project isolates DeepSeek proof-of-work from HTTP request construction.
2. **Use the site's own algorithm where feasible.** Its PoW solver runs the DeepSeek WASM algorithm (`DeepSeekHashV1`) rather than duplicating the algorithm by guesswork.
3. **Web API envelope errors are independent of HTTP status.** The client validates outer code, business code, and `biz_data`; HTTP 200 alone is not success.
4. **Tool parsing must be incremental for streaming.** The parser holds a bounded window while deciding whether partial output may become a tool marker.
5. **Unicode-normalized dialect matching is necessary.** It explicitly treats U+FF5C full-width pipe as `|` and U+2581 as `_`, matching the exact class of failures observed earlier with Kilo/DSML.
6. **Bound parser memory.** Tool XML buffering has an explicit maximum (`MAX_XML_BUF_LEN`), preventing malformed/truncated output from growing without limit.
7. **Keepalive behavior matters while buffering a tool call.** The parser has an explicit keepalive interval so a client is not left silent while the gateway withholds ambiguous tool syntax.
8. **Provider configuration can expose extra start/end tool markers.** Dialect support is extensible rather than hard-coded to a single format.

Transfer status:

- DeepSeek provider knowledge: **already independently validated in our DeepSeek project; use as additional corroboration**
- Incremental marker hold window: **adopt for native streaming providers**
- Parser memory bound + keepalive: **adopt**
- Configurable dialect marker set: **adopt**

### `tashfeenahmed/freellmapi` — `D:\Tools\025-freellmapi`

This project contains one of the strongest reusable tool-normalization test suites in the corpus.

Observed dialect-rescue support:

- Kimi/DeepSeek token dialect: `<|tool_call_begin|>...`
- Llama/Groq function tags: `<function=NAME{...}</function>`
- Qwen/Hermes XML: `<tool_call>{...}</tool_call>`
- Bare/fenced JSON only when the named function is in the request's declared tool set

Important lessons:

1. **Never infer a tool call that the request did not declare.** The parser is schema-gated against the tool set.
2. **An empty tool set means nothing is callable.** A past bug treated an empty set as wildcard; tests explicitly prevent recurrence.
3. **Detected-but-unparseable tool dialect is not normal prose.** It is a dead/ambiguous turn that should trigger controlled recovery/failover rather than leaking garbage to the client.
4. **Streaming needs a hold-window classifier.** It separately asks whether text already starts with a dialect marker or could still grow into one; only divergent normal prose may be flushed immediately.
5. **Balanced JSON parsing must be string-aware.** Brace counting must respect quoted strings and escapes.
6. **Ordinary JSON answers must pass through.** Bare JSON is only converted into a tool call when the tool name is actually declared.
7. **Cross-model continuation changes dialect.** A model selected after failover may continue the previous model's private tool syntax, so normalization belongs at the gateway boundary rather than in one provider implementation.

Transfer status:

- Multi-dialect rescue layer: **adopt as shared gateway library**
- Empty-tool-set fail-closed rule: **adopt and regression-test**
- Detected-but-unparseable = protocol failure: **adopt**
- Streaming hold-window logic: **adopt**

### `Amm1rr/WebAI-to-API` — `D:\Tools\029-webai-to-api`

Important architectural split observed:

- Browser-native request executor is isolated from provider-specific hooks.
- A Gemini backend adapter exists separately from browser execution and uses a web API client/session registry.

Browser executor lessons:

1. **Use request-scoped state.** It tracks request ID, start time, whether a permit was acquired, cleanup state, page poison state, queue depth, conversation reuse, observer readiness and submission confirmation.
2. **Separate timeouts by phase.** Navigation, UI-ready wait, per-chunk wait and total request timeout are independent configuration values.
3. **Session/page lease is an explicit resource.** A request acquires a lease and invalidates poisoned tabs after crash/close rather than blindly reusing them.
4. **Backpressure must be bounded.** Observer events use a bounded queue (`maxsize=100`) and track dropped chunks/max depth.
5. **Browser crash/close is a state transition, not a generic exception.** The active tab is marked poisoned/invalidated.
6. **Submission confirmation is explicit.** This complements the commitment-boundary lesson already transferred from AWA.
7. **Backend and DOM should be separate adapter choices.** Gemini's direct web API adapter is a different backend implementation rather than hidden inside browser logic.
8. **Conversation snapshots need schema versioning and provider identity validation.** Restoring state without both can create cross-provider/state-corruption bugs.

Transfer status:

- Request-state object + phase timeouts: **adopt**
- Page/session lease abstraction: **adopt for DOM fallback transports**
- Bounded stream queue/backpressure metrics: **adopt**
- Snapshot schema version/provider validation: **adopt when persistent conversations are added**
- Backend-vs-browser transport separation: **adopt as core provider architecture**

### `justlovemaki/AIClient-2-API` — `D:\Tools\007-aiclient2api`

Important lessons:

1. **Treat OpenAI Responses as a first-class protocol, not a thin alias.** A dedicated converter maps Responses requests/responses/stream events across OpenAI, Claude, Gemini, Codex and Grok protocols.
2. **`instructions`, `input`, `max_output_tokens`, parallel tool calls and typed input items need explicit normalization.** Mapping Responses to Chat Completions is non-trivial.
3. **Streaming conversion needs per-protocol state.** The converter keeps stream state for protocols whose events cannot be translated statelessly.
4. **Protocol conversion belongs above provider transport.** This supports one unified gateway without contaminating provider-specific backend code.

Transfer status:

- `/v1/responses` compatibility layer: **adopt**
- Protocol conversion registry: **adopt before all four providers are integrated**

### `chenyme/grok2api` — `D:\Tools\064-grok2api`

Important resilience lessons from the gateway service:

1. **Retry budget should distinguish account-specific vs provider-wide failures.** A provider-wide stream idle failure should not rotate through an entire account pool and multiply the same long timeout.
2. **Use failure fingerprints.** Repeated equivalent non-account failures are capped; this prevents expensive retry storms.
3. **A downstream HTTP 2xx can still terminate with an in-stream provider failure.** The service carries a `StreamFailureDiagnostic` separately from HTTP status.
4. **Finalize usage/audit independently of response delivery.** The result object exposes `Finalize`, first-token marking and stream-failure recording callbacks.
5. **Retry limits are explicit policy.** Unlimited routing is an explicit sentinel, not accidental `<=0` behavior.
6. **Error bodies need redaction and size limits before audit.** Failure diagnostics should not become a data-exfiltration path.

Transfer status:

- Failure fingerprinting: **adopt**
- Separate account/provider failure classes: **adopt for account-pooled providers**
- Stream failure after 2xx: **adopt into common stream state machine**
- Finalization hooks: **adopt into observability layer**

### `y13sint/FreeQwenApi` — `D:\Tools\042-qwen-api`

This project is useful as a transitional design between browser bootstrap and direct backend calls.

Observed pattern:

- A browser context is used to obtain/store the Web token from local storage.
- Actual task/status requests are executed with `fetch()` inside the browser context using Bearer authorization.
- A page pool is maintained for browser resources.

Important lesson:

**The browser can be used as a credential/session bootstrap and same-origin execution environment without making the DOM the inference transport.** This is an important intermediate fallback when direct host-side HTTP lacks browser-bound state or anti-bot context.

Recommended transport hierarchy derived from this project and the rest of the corpus:

1. Direct host HTTP/WebSocket to web backend
2. Browser-context `fetch`/XHR against backend using the logged-in browser session
3. Network interception/response capture
4. DOM submit/read only as last fallback

### `Sophomoresty/gemini-web2api` — `D:\Tools\057-gemini-web2api`

Source-inspected backend route:

`https://gemini.google.com[/u/<account>]/_/BardChatUi/data/assistant.lamda.BardFrontendService/StreamGenerate`

Observed request characteristics:

- `application/x-www-form-urlencoded`
- Origin/Referer/X-Same-Domain browser headers
- request build/version (`bl`) parameter
- account prefix support
- optional cookie + SAPISID-derived authorization
- model selection encoded through positional payload fields rather than a clean public JSON schema

Important lessons:

1. **Backend build identifiers drift.** The project fetches the Gemini page and extracts the current `boq_assistant-bard-web-server_*` build ID, then retries with the refreshed value.
2. **Web backends may use positional/RPC-style payloads.** Provider adapters must isolate such wire formats from the gateway schema.
3. **Authenticated and anonymous backend paths can have different capability ceilings.** Capability discovery must be tied to the actual session/account state, not a static model list.
4. **Tool-call parsing requires full response buffering in this implementation.** It deliberately uses a single streaming chunk when tools are enabled because the complete output must be parsed first. This reinforces truthful `streaming_mode` metadata.
5. **One backend can serve multiple outward compatibility protocols.** This implementation exposes Chat Completions, Responses, and Google-native generation from the same web backend.

Transfer status:

- Runtime backend-version discovery: **adopt conceptually for provider-specific volatile identifiers**
- Wire-format isolation: **adopt**
- Capability tied to session state: **adopt**

### `diegosouzapw/OmniRoute` — `D:\Tools\018-omniroute`

Two high-value lessons were source-inspected.

**Unified browser fingerprint:**

The Claude Web implementation keeps a single fingerprint source of truth because Cloudflare clearance is bound not only to the cookie but also to User-Agent, TLS/JA3 fingerprint and IP. A fingerprint version is bumped whenever the profile changes so cached clearance is invalidated.

**Origin-scoped fetch interceptor:**

Tests enforce that an injected Authorization token is added only to normalized inference paths under the configured base origin/path. Similar-prefix URLs, other tenants/origins and suffix-spoofed paths must not receive credentials. Caller-supplied Authorization is replaced for owned provider routes.

Important lessons:

1. **Session artifacts and client fingerprint form one identity bundle.** Cookie reuse with a changed UA/TLS/IP can fail even if the cookie value is valid.
2. **Version fingerprint state.** A cached challenge/session should record the fingerprint version that created it.
3. **Credential injection must be origin + normalized-path scoped, fail-closed.** String prefix matching alone is unsafe.
4. **Provider-owned credentials must override untrusted caller headers on owned upstream routes.**

Transfer status:

- Fingerprint bundle/version: **adopt for anti-bot-sensitive providers**
- Origin/path scoped credential policy: **adopt into backend transport core before Qwen/Z.ai production use**

## Cross-project synthesis

### Backend-first provider state machine

The corpus supports the following common provider lifecycle:

`DISCOVER -> SESSION_READY -> CREATE/RESUME CONVERSATION -> SUBMIT -> FIRST_EVENT -> STREAMING -> TERMINAL -> CLEANUP`

Each transition needs an explicit timeout/error class. `HTTP 200` is not terminal success.

### Transport preference

The engineering default for this program should be:

1. **Direct backend HTTP/SSE/WebSocket**
2. **Browser-context fetch/XHR** when session state is browser-bound
3. **Network interception/capture** when direct replay is not yet understood
4. **DOM control** only when the backend route cannot yet be reproduced safely/reliably

DOM remains useful for login, challenge/bootstrap, model selection where no stable backend equivalent is known, and final fallback—not as the first choice for message transport.

### Shared stream contract

Every provider stream should track at minimum:

- request/correlation ID
- header-ready timestamp
- first parsed event timestamp
- last meaningful event timestamp
- bytes received
- parsed event count
- first-token timestamp
- terminal reason
- in-stream error if any
- client disconnect/cancel state

Use separate header, first-event, idle and total timeouts.

### Shared tool normalization contract

Normalize before exposing to clients:

1. Canonicalize Unicode/markup corruption.
2. Detect dialect markers incrementally.
3. Parse only against the request's declared tool set.
4. Validate/coerce arguments against tool schema.
5. Reject missing required fields and malformed JSON.
6. De-duplicate repeated calls.
7. Preserve surrounding prose only when the target protocol permits it.
8. If a dialect is detected but cannot be safely parsed, report a protocol error or bounded repair; do not leak raw dialect as a successful final answer.
9. Bound parser memory and provide keepalive behavior while ambiguous tool syntax is buffered.
10. Render normalized calls separately for Chat Completions and Responses API.

### Shared security contract for backend access

- Never inject credentials by raw URL prefix alone.
- Match normalized origin + path policy.
- Treat cookies, UA/client hints, TLS profile, IP/proxy and anti-bot challenge state as one session/fingerprint bundle where applicable.
- Redact credentials from logs.
- Cap logged upstream error bodies.
- Fail closed on unknown provider/model/origin.

### Retry contract

- Retry only before the commitment boundary or when the upstream explicitly proves non-acceptance.
- Separate account-local failures from provider-wide failures.
- Use a bounded retry budget and failure fingerprints.
- Do not rotate across an entire account pool for the same provider-wide stream-idle failure.
- A failure embedded after downstream 2xx must still finalize as failed/partial, not successful.

## Immediate implications for the unified gateway

### ChatGPT Web

Current DOM provider should remain supported but be reframed as fallback transport. Research should now prioritize reproducing the actual ChatGPT web backend request/stream using the authenticated browser session, with DOM retained for bootstrap/fallback.

### DeepSeek Web

We already have an independently proven backend-first implementation. The next architectural step is to migrate it into the common Provider interface rather than reimplement it through DOM.

### Qwen Web

The corpus provides enough implementation detail to begin a backend-first provider immediately. `qwen2API` is the primary reference; `FreeQwenApi` is useful for browser-session bootstrap fallback.

### Z.ai Web

No equally mature Z.ai-specific source was identified in this first deep pass. Use the same discovery protocol: capture network from a logged-in browser, identify session/bootstrap calls and streaming backend, reproduce read-only/low-risk calls first, and use DOM only until the backend contract is established.

## Evidence classification

- GitHub metadata: live public metadata collected 2026-09-10.
- Project lessons above: source-inspected implementation evidence from local clones.
- No external project's backend functionality is claimed as currently working merely from source inspection.
- Any pattern transferred into `mcp-web-bridge` must receive local unit/integration tests (E1) and live provider E2 before being advertised as operational.
