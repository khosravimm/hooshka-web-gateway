# Changelog

All notable changes to mcp-web-bridge are recorded here.

## 0.4.3 - 2026-09-10

### Added
- `zai-web` provider with browser-frontend/backend-SSE capture transport.
- `zai_web` provider type and service wiring.
- Z.ai model discovery through browser-context fallback when direct HTTP receives provider/session rejection.
- Dedicated Z.ai Chrome CDP runtime management on `127.0.0.1:9223` via `service_manager.ps1`.
- DeepSeek account-suspension incident document and Web-chat risk-budget controls.

### Changed
- Z.ai is now enabled for basic chat completion and buffered stream compatibility only; tools, search, vision and files remain disabled until dedicated E2 acceptance.
- VERSION bumped to 0.4.3 for the first three-provider service baseline: ChatGPT Web, Qwen Web, and Z.ai Web.

### Evidence
- Deterministic suite: 53/53 PASS.
- Service restart starts/verifies dedicated Z.ai Chrome CDP; `/json/version` returned Chrome/152.0.7977.84.
- `/ready`: PASS with `zai-web`, `qwen-web`, and `chatgpt-web` all ready.
- `/v1/models`: PASS with 16 Z.ai provider models.
- Z.ai gateway non-stream E2: PASS (`ZAI_SERVICE_E2_OK`).
- Z.ai gateway SSE compatibility E2: PASS (`ZAI_STREAM_E2_OK`, 2 data frames plus `[DONE]`).
- No DeepSeek completion E2 claim is made while the current account is suspended/muted.
- No E3 long-duration reliability claim is made.

## 0.4.2 - 2026-09-10

### Fixed
- Qwen `openNewChat()` is now isolated as a pre-submit phase; navigation/context loss is recovered before submission, so `beforeSendMessage()` is never replayed after the commitment boundary.
- Qwen frontend controller bootstrap now performs bounded pre-submit retries when the dynamically imported `main.js` module transiently fails to load from the frontend CDN.
- Qwen `thinking=false` now maps to the frontend-supported `Fast` mode while retaining the Thinking feature context; `thinking=true` maps to `Auto`.
- Qwen request metadata refreshes session state before submit so guest/authenticated provenance is not left as `unknown` after service restart.

### Evidence
- Deterministic suite: 50/50 PASS.
- Three independent fresh Qwen browser bootstrap checks: 3/3 PASS.
- Windows service restart: PASS; listener remained `127.0.0.1:5000`.
- Gateway Qwen non-stream repeated smoke: 3/3 PASS, guest session provenance observed.
- Gateway Qwen SSE smoke: PASS with terminal `[DONE]`.
- Wire-level thinking verification: `false -> Fast, thinking_enabled=false, auto_thinking=false`; `true -> Auto, thinking_enabled=true, auto_thinking=true`; both requests completed E2E.
- Evidence is E2 within this execution window only; no E3 reliability claim.
## 0.4.1 - 2026-09-10

### Added
- Shared `core.upstream_response` classifier for HTTP status, content type, and application-level envelopes before SSE parsing.
- Explicit `account_local_muted`, `application_error`, `rate_limit`, `provider_wide`, and `unexpected_content_type` dispositions.
- Technology/Experience Matrix covering all 80 unique GitHub repositories in the current `D:\Tools` metadata inventory, with technical fields populated only where source inspection has actually occurred.

### Research
- DeepSeek live PoC session creation still succeeds, but current completion returns HTTP 200 with `application/json` and an account-local muted envelope rather than SSE. This is now treated as a terminal application failure, not an empty successful stream.
- Z.ai current frontend observed as `prod-fe-1.1.93`. Live `/api/models` returned 15 models and capability metadata; current completion source uses `/api/chat/completions`, `X-FE-Version`, `X-Signature`, and device/session context.
- A controlled Z.ai UI submission for network discovery created `/api/v1/chats/new` successfully, then entered Aliyun CAPTCHA before completion. No CAPTCHA bypass was attempted and Z.ai completion is not declared operational.

### Tests
- Deterministic suite: 47/47 PASS.
- No DeepSeek or Z.ai E2 completion claim is made in this release.

## 0.4.0 - 2026-09-10

### Added
- `qwen-web` provider with a backend-first browser-controller transport using Qwen's own frontend controller rather than DOM chat automation.
- Dedicated ignored Qwen browser profile suitable for headless service execution; no personal-browser credential export is required for guest-mode chat.
- Runtime frontend discovery for the current Qwen `main.js` module and frontend version.
- Qwen phase-specific first-event, meaningful-idle, and total timeouts for reconstructed streaming.
- Qwen thinking/search feature state is driven through the frontend's own feature manager API rather than UI controls.

### Changed
- Unified provider registry now wires `qwen_web` alongside the existing ChatGPT provider.
- `/modes` exposes search/reasoning/files/transport provenance in addition to existing capability metadata.
- Qwen streaming provenance is explicitly `reconstructed`; the browser controller consumes the provider's native SSE internally, while the bridge emits deltas reconstructed from controller state.

### Evidence
- Deterministic regression suite: 42/42 PASS after Qwen wiring and feature-state remediation.
- Windows service restart: PASS; service remained `Running` and listener remained restricted to `127.0.0.1:5000`.
- Gateway `/ready`, `/modes`, `/v1/models`: PASS with `qwen-web` advertised as `browser_backend_controller`, `reconstructed`, `tools=false`.
- Qwen gateway non-stream E2E: PASS (`QWEN_GATEWAY_NONSTREAM_OK`).
- Qwen gateway SSE E2E: PASS (`QWEN_GATEWAY_STREAM_DIAG` plus terminal `[DONE]`).
- Qwen thinking off/on E2E: PASS.
- Unknown model and unsupported Qwen tools: fail closed with HTTP 400.
- Search request completed E2E, but search capability remains disabled until independent search-event provenance is captured.
- No E3 claim is made.

## 0.3.0 - 2026-09-10

### Added
- Operational liveness/readiness/deep-health endpoints.
- Environment-based runtime API authentication support; runtime secrets no longer belong in tracked configuration.
- OpenAI-compatible tool protocol serialization and normalization for JSON and observed DSML variants.
- Strict machine envelopes for tool calls/final answers and bounded protocol repair for required tool calls.
- Strong-signal-only auto-tool review, informed by AWA live experience; broad retry is intentionally avoided.
- Commitment-aware retry boundary: failures after submission starts are not replayed automatically.
- Exact fail-closed model/provider routing in preparation for a multi-provider gateway.
- Incremental HTTP SSE pass-through queue so the HTTP layer does not re-buffer provider streams.
- Regression tests for tool normalization, routing, and retry/commitment behavior.
- Waitress production WSGI runtime for the Windows service.

### Changed
- Service bind restricted to 127.0.0.1 by default.
- ChatGPT Web canonical gateway model is `chatgpt-web`; arbitrary unproven model aliases are no longer treated as routable.
- ChatGPT DOM completion detection now waits for a completed/stable response instead of accepting transient `Thinking` UI state.
- Large agent/tool manifests are submitted atomically using composer fill semantics rather than character-by-character typing.
- Windows service management aligned with the actual NSSM deployment.

### Fixed
- Governance crash caused by legacy string identity values where an identity object was expected.
- Tool definitions, system messages, assistant tool calls, and tool results being lost before reaching ChatGPT Web.
- DOM streaming path discarding `tool_calls` / returning the wrong finish reason.
- Stale React locator races while waiting for ChatGPT responses.
- Duplicate-turn risk from automatic retry after an ambiguous post-submit failure.
- HTTP streaming layer collecting the complete async stream before sending SSE frames.
- Missing `requests` dependency that prevented the repository test suite from collecting.

### Evidence
- Deterministic suite: 42 tests passing before version documentation freeze; rerun required after any subsequent code change.
- Live ChatGPT Web smoke: exact `ROUTING_OK` response.
- Live routing negative tests: unknown model 400; unknown provider 400.
- Live tool round-trip: tool call -> supplied `ROUNDTRIP_OK` tool result -> final `ROUNDTRIP_OK` with zero repeated tool call.
- Live SSE tool-call: `delta.tool_calls`, `finish_reason=tool_calls`, and `[DONE]` observed.
- Windows service: Waitress 3.0.2 bound to 127.0.0.1:5000.

## Earlier history

The repository did not maintain a formal VERSION/CHANGELOG contract before 0.3.0. Earlier commits remain the source of truth for pre-0.3.0 history.
