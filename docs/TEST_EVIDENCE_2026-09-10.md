# Test Evidence — 2026-09-10

## Scope
Operational remediation of the ChatGPT Web provider and preparation of `mcp-web-bridge` as the foundation for a unified Web Chat API.

## Evidence classification
- Deterministic unit/regression tests: **E1**.
- Real local gateway -> real authenticated ChatGPT Web -> gateway response tests: **E2**.
- No E3 claim is made. Repeated multi-window reliability thresholds have not yet been defined and met.

## E1 regression evidence
Latest pre-freeze run:

```text
42 passed in 0.54s
compileall: PASS
```

Covered regressions include:
- legacy governance identity normalization;
- JSON tool call parsing;
- fullwidth/escaped multi-DSML parsing;
- full transcript + tool result serialization;
- strong-signal auto-tool classification;
- ordinary-final no-retry behavior;
- false tool-refusal detection;
- post-submission no-replay vs pre-submission bounded retry;
- exact model routing;
- empty supported-model list is not a wildcard;
- no implicit cross-provider model fallback.

## E2 runtime/API evidence
Windows service: `WebLLMBridge`.

Validated runtime state:
- service status: Running;
- host: `127.0.0.1`;
- port: `5000`;
- WSGI: Waitress 3.0.2;
- current log startup: `Serving on http://127.0.0.1:5000`.

Validated API semantics:
- `/health`: 200;
- `/ready`: 200;
- `/health/deep`: 200;
- `/modes`: 200 with valid auth;
- `/v1/models`: 200;
- invalid auth: 401;
- empty messages: 400;
- unknown model: 400 `unknown_or_unsupported_model`;
- unknown provider: 400 `unknown_provider`;
- canonical advertised model: `chatgpt-web` only.

### Basic live chat
Input requested exact marker `ROUTING_OK`.
Result:
```text
HTTP 200
finish_reason=stop
content=ROUTING_OK
```

### Auto-tool placement after AWA strong-signal policy
Three live cases:
1. Explicit request naming `bash` -> `finish_reason=tool_calls`, one bash call.
2. Plain arithmetic (`2+2`) -> `finish_reason=stop`, content `4`, zero tool calls.
3. Local WSL state request -> `finish_reason=tool_calls`, one bash call containing read-only WSL/Windows feature checks.

This is evidence that strong-signal review recovers required tool usage without broadly converting ordinary final answers into tool calls.

### Full live tool round-trip
First turn:
```text
HTTP 200
finish_reason=tool_calls
tool=bash
arguments={"command":"Write-Output ROUNDTRIP_OK"}
```

A tool result of `ROUNDTRIP_OK` was supplied in the second OpenAI-compatible turn.
Second turn:
```text
HTTP 200
finish_reason=stop
tool_count=0
content=ROUNDTRIP_OK
```

This validates preservation of assistant tool_calls + tool result + continuation through ChatGPT Web.

### Streaming tool-call
With `stream=true`:
```text
HTTP 200
SSE frames: 1 data frame + [DONE]
delta.tool_calls: present
finish_reason=tool_calls
tool=bash
```

First frame arrived after approximately 33 seconds because the ChatGPT DOM transport is currently buffered compatibility streaming. The HTTP bridge no longer collects the provider stream before yielding; this does **not** convert the DOM provider into native token streaming.

### Shutdown lifecycle
Before Waitress/cleanup changes, historical logs contained:
`Task was destroyed but it is pending!`
for Playwright connection tasks during service restart.

After adding provider close-before-loop-stop, a live request was performed and the service restarted at 2026-09-10 18:22:50 local. New startup lines showed registration and Waitress serving without a new pending-task destruction error in the inspected post-marker log range.

## Remaining acceptance work before four-provider release
- Add a deterministic delayed mock-provider HTTP test proving first SSE data is observable before the provider finishes.
- Add phase-specific timeout telemetry/controls (readiness, first-response, idle, total) rather than one coarse provider timeout.
- Harden browser origin/session isolation for additional providers.
- Implement sanitized observability/evidence boundary that excludes raw prompts/tool args by default.
- Add `/v1/responses` compatibility based on AWA experience if required by target agent clients.
- Integrate existing DeepSeek Web implementation as a provider.
- Implement and E2-test Qwen Web and Z.ai Web providers.
- Define E3 acceptance thresholds and repeat tests across independent time windows.

## Qwen Web provider evidence — 0.4.0

Evidence level: **E2 for basic chat/non-stream/stream and thinking controls; E1/E0 or pending for remaining acceptance items.** No E3 claim.

Observed current Web protocol:
- frontend version: `0.2.91`;
- auth probe: `/api/v1/auths/`;
- model endpoint: `/api/v2/models/`;
- create chat: `POST /api/v2/chats/new`;
- completion: `POST /api/v2/chat/completions?chat_id=<id>`;
- completion content type: `text/event-stream`;
- observed SSE phases: `thinking_summary`, `answer`.

Transport decision:
- direct HTTP: researched, not operationally accepted due browser/BX/WAF coupling;
- raw browser-context fetch: chat creation encountered challenge behavior;
- selected transport: `browser_backend_controller` using Qwen's own frontend controller inside a dedicated headless profile;
- DOM typing/clicking: not used for the implemented inference path.

Live service evidence after restart:
```text
42 passed
service=Running
listener=127.0.0.1:5000
/ready=ready
qwen-web transport=browser_backend_controller
qwen-web streaming_mode=reconstructed
qwen-web tools=false
non-stream exact marker=PASS
stream SSE data + [DONE]=PASS
thinking=false exact marker=PASS
thinking=true exact marker=PASS
unknown model HTTP 400=PASS
tools requested while tools=false HTTP 400=PASS
```

Search-enabled request completed, but search capability intentionally remains `false` until a search-specific network/event trace proves the feature was actually exercised. Tool calling, multiple tools, malformed tool dialects, session expiry/authenticated-session behavior, upstream 429/401/403 fault injection, cancellation/cleanup, and repeated E3 reliability windows remain acceptance work and must not be represented as passed.
