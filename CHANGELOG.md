# Changelog

All notable changes to Hooshka Web Gateway are recorded here. `mcp-web-bridge` is the legacy compatibility identity during migration.

## 0.7.6 - 2026-09-16

### Fixed
- Changed the Control Panel provider Test action from full provider `health_check()` to a bounded CDP runtime probe.
- Provider Test now updates only the clicked provider row and always restores the button state in `finally`.
- Added browser-side abort timeout and inline OK/FAILED/ERROR status instead of modal-only feedback.
- Added selectable upstream model options for Qwen and Z.ai provider default-model pickers.

### Validation
- Control Panel Test no longer initiates Web Chat completion or long Playwright provider work.

## 0.7.5 - 2026-09-16

### Added
- Control Panel provider table now exposes editable Default Model controls backed by provider configuration.
- Added `PUT /panel/api/providers/<provider_id>/model` with validation against selectable provider model options.
- Provider payloads now include model defaults and selectable options for UI use.

### Validation
- Added regression tests for Control Panel provider model state, editable UI contract, API route, validation, and persistence path.
- Full Gateway suite: 140 passed.

## 0.7.4 - 2026-09-16

### Fixed
- Fixed Gateway worker-pool starvation where stuck browser/provider work could make `/health`, `/ready`, and `/v1/models` time out.
- Added bounded provider work slots with immediate `503 provider_busy` backpressure instead of unbounded HTTP worker queue growth.
- Changed `/ready` to a fast static readiness endpoint and moved browser/provider probing to bounded `/health/deep`.
- Changed `/v1/models` to fast static discovery so model selectors do not block on live browser sessions.
- Added provider runtime counters to `/health`, `/ready`, and `/v1/models` for inflight, rejected, and timeout diagnostics.

### Evidence
- Regression tests cover fast health/ready/models and provider slot acquire/release paths.
- Root-cause evidence before the fix showed Hooshka Web Gateway `Task queue depth` growth and Playwright `EPIPE`/closed-pipe errors while `/health` timed out.

## 0.7.3 - 2026-09-16

### Fixed
- Removed all Control Panel runtime CDN dependencies.
- Replaced CDN Tailwind usage with a local inline CSS utility baseline.
- Replaced FontAwesome icons with lightweight inline text badges.
- Replaced Chart.js dependency with a native Canvas request chart.

### Validation
- Control Panel Python template compiles without warnings.
- No `https://`, `cdn`, `font-awesome`, `fas fa`, `new Chart(` or `requestsChart` runtime dependency remains in `control_panel.py`.
- Isolated headless Chrome validation uses a temporary profile and does not touch user/provider browser tabs.

## 0.7.2 - 2026-09-16

### Added
- Control Panel header now shows release version, git commit, branch and current evidence label.
- Overview now shows Ready Providers and per-provider runtime/CDP readiness.
- Providers tab now has a dedicated Runtime column with CDP URL and readiness state for each Web Chat provider.
- Added `GET /panel/api/meta` for panel metadata.
- Added an inline empty favicon to avoid the browser's default `/favicon.ico` 404.

### Changed
- Widened the panel shell from the previous narrow dashboard layout to a 1680px operations-oriented layout.

### Validation
- Full gateway suite: 131 passed.
- Isolated headless Chrome render test with a temporary profile confirmed version/commit header, Ready Providers, runtime summary, provider table, all four provider IDs and all four CDP URLs.
- `/panel/api/meta` reports `version=0.7.1` before this release bump, `commit=8c7109c`, `branch=master`; after tagging, the same endpoint reports the current checked-out commit.
- `/panel/api/providers` reports all four provider CDP runtimes ready: ChatGPT 9224, Qwen 9225, Z.ai 9223 and DeepSeek 9226.

### Known Debt
- The panel still uses CDN-hosted Tailwind/Chart.js/FontAwesome assets. External CDN network errors do not break the local panel contract, but asset bundling remains a production-hardening task.

## 0.7.1 - 2026-09-16

### Fixed
- Allow true loopback clients (`127.0.0.1`, `::1`, `localhost`) to call local Hooshka Web Gateway endpoints without a bearer token.
- Keep non-loopback requests protected by the existing bearer-token authentication path.
- ChatGPT reasoning-effort control now survives current composer UI drift by resolving the visible effort pill near the active composer and using a bounded verified fallback click path.
- DeepSeek DeepThink/Search control now covers current `.ds-toggle-button` surfaces and re-resolves toggles after React node replacement.

### Evidence
- Authenticated Thinking/Search matrix: 4/4 PASS for Qwen Web, ChatGPT Web, DeepSeek Web and Z.ai Web.
- Qwen Web matrix used `qwen-web` with verified backend `qwen3.8-max`.
- ChatGPT Web matrix verified `thinking_effort_index` 0/1 and search state in `provider_meta.features`.
- DeepSeek Web matrix verified all four requested states in `provider_meta.features`.
- Z.ai Web matrix used exact model `zai:glm-5.3` and verified backend feature fields: `enable_thinking`, `reasoning_effort`, `web_search`, `auto_web_search`.
- Detailed feature evidence is recorded in `docs/WEBCHAT_FEATURE_MATRIX_E2_2026-09-16.md`.

### Validation
- Added middleware tests for localhost bypass and non-loopback 401 behavior.
- Targeted deterministic feature-control suite: 42 passed.
- Full gateway suite: 131 passed.

## Unreleased

### Fixed
- Gateway restart now preserves authenticated provider CDP runtimes instead of deliberately stopping ChatGPT/Z.ai browser sessions; explicit `stop` and `uninstall` still close project-owned runtimes.
- Qwen provider metadata now reports the effective Thinking/Search booleans for both sidecar and browser-controller transports.

## 0.7.0 - 2026-09-15

### Added
- Normalized per-provider `thinking` and `search` feature defaults.
- Request-level `thinking` and `search` overrides for `/v1/chat/completions`, `/v1/chat/code`, and `/v1/chat/conversation`.
- `GET/PUT /v1/providers/<provider-id>/features` for reading and persisting feature defaults.
- Control Panel switches for Thinking and Search on every registered Web Chat provider.
- Provider feature-state reporting under `/modes`.
- `docs/WEBCHAT_FEATURE_CONTROLS.md` with provider mappings, fail-closed rules and evidence levels.

### Changed
- ChatGPT maps `thinking=false` to the minimum available reasoning effort and controls Web Search through the composer selection surface with post-change verification.
- Qwen uses its existing browser-controller thinking/search flags under the common feature contract.
- Z.ai rewrites only the authenticated frontend completion feature flags (`enable_thinking`, `reasoning_effort`, `web_search`, `auto_web_search`) before the Web Chat request is sent.
- DeepSeek has DeepThink/Search UI-control wiring, but remains E2-pending while the project account is suspended.

### Fixed
- ChatGPT composer verification now compares normalized content rather than raw character length, reducing false mismatches caused by whitespace, NBSP and zero-width characters.
- Canonical documentation now reflects the actual local checkout path and current provider certification state.
- Documentation index mojibake and duplicate Stop Contract entries were removed.
- The deterministic compile gate excludes ignored `.runtime/` operational artifacts from release-source validation.
- Service-manager CDP ownership now recognizes the two known Hooshka Web Gateway checkout roots without weakening the non-project Chrome guard.

### Evidence
- Deterministic suite: 129 passed.
- ChatGPT control-only live test: Thinking/Search `off -> on -> off` verified without submitting a user message.
- Public feature API persisted and restored Qwen defaults; Control Panel Thinking and Search switches were each exercised independently and restored to `false/false`.
- Post-restart `/health`, `/ready`, and `/modes` passed with four providers and feature state exposed for all four.
- Z.ai authenticated frontend payload observation confirmed the native feature fields used by the Web Chat request.
- DeepSeek feature controls are implementation/E1 only until authenticated E2 retest is possible.
- No E3 reliability claim is made.

## 0.6.6 - 2026-09-11

### Fixed
- Kilo Code compatibility for text-only Web providers: optional tool schemas are now dropped for providers that do not support tool calling when `tool_choice` is not required.
- Improved unsupported-capability errors with requested tool details.
- Kilo local Hooshka model metadata now marks `qwen*` and `zai*` as `tool_call=false`, while `chatgpt-web` remains `tool_call=true`.

### Evidence
- Kilo Code + `hooshka/qwen-web`: PASS with `KILO_CODE_QWEN_OPTIONAL_TOOLS_OK`.
- Kilo Code + `hooshka/zai-web`: PASS with `KILO_CODE_ZAI_OPTIONAL_TOOLS_OK`.
- Deterministic unit suite: 70 passed.
- Required tool calls remain fail-closed for Qwen/Z.ai; no tool-calling support claim is made for these providers.

## 0.6.5 - 2026-09-11

### Added
- Project-owned Qwen Web Chrome/CDP runtime on port `9225` with dedicated profile `.runtime\qwen-profile`.
- Qwen CDP transport reuse path so the authenticated project browser session is not relaunched as a separate headless profile.
- Qwen authenticated Kilo CLI E2 evidence for `qwen:qwen3.8-max`.

### Changed
- Qwen profile shutdown now prefers graceful CDP close before force cleanup to reduce session persistence risk.
- Kilo Hooshka model map now includes authenticated Qwen upstream model ids.
- Removed Hooshka API key from Kilo provider options; credential remains in Kilo auth store.

### Evidence
- Qwen official-login session check: `authenticated=true`, HTTP 200.
- Direct Gateway `qwen:qwen3.8-max` completion: PASS with `QWEN_LOGIN_PERSIST_OK`.
- Kilo CLI `--agent summary` + `hooshka/qwen:qwen3.8-max` E2: PASS with exact output `KILO_HWG_QWEN_MAX_OK`.
- Qwen model evidence aligned: upstream/backend `qwen3.8-max`, session `authenticated`.
- No password, cookie, bearer token, provider token, signature, CAPTCHA proof, or full provider request body is stored in tracked files.
- No E3 reliability claim is made.

## 0.6.4 - 2026-09-11

### Added
- Project-owned ChatGPT Web Chrome/CDP runtime on port `9224` with dedicated profile `.runtime\chatgpt-profile`.
- ChatGPT large-agent-prompt backend-intercept transport for Kilo and other OpenAI-compatible agent clients.
- `docs/KILO_E2_EVIDENCE_2026-09-11.md` with current Kilo CLI E2 results.

### Changed
- ChatGPT Web no longer attaches to shared/legacy CDP port `9222` by default.
- Service manager now enforces CDP port ownership for ChatGPT and Z.ai before attach/start.
- Kilo test guidance now distinguishes tool-required `code` agent tests from text-only `summary` agent tests.

### Evidence
- Deterministic regression suite: 63/63 PASS.
- `git diff --check`: PASS.
- ChatGPT authenticated profile: PASS.
- Kilo CLI `hooshka/chatgpt-web` E2: PASS with exact output `KILO_HWG_CHATGPT_OK`.
- Kilo CLI `--agent summary` + `hooshka/zai:glm-5.3` E2: PASS with exact output `KILO_HWG_ZAI_GLM53_OK`.
- Z.ai model evidence aligned: requested/upstream/backend `glm-5.3`, UI label `GLM-5.3`, session `authenticated`.
- Qwen completion was not executed because current Qwen profile status is `guest` / HTTP 401.
- No E3 reliability claim is made.

## 0.6.3 - 2026-09-10

### Security / Governance
- Added mandatory authenticated-session policy for Web-chat providers.
- Added `require_authenticated: true` for Qwen Web and Z.ai Web in `config.yaml`.
- Qwen browser-controller completion now fails closed with `auth_required` when the session is guest/unauthenticated.
- Added official `LOGIN_SESSION_GUIDE.md` for provider login and session persistence using dedicated browser profiles.
- Updated Kilo and Start Here guidance so guest mode is not considered valid operation.

### Evidence
- Deterministic regression suite: 63/63 PASS.
- Added negative test proving Qwen guest mode is rejected by policy.
- No credentials, cookies, provider tokens, authorization headers or CAPTCHA proof are stored in tracked files.

## 0.6.2 - 2026-09-10

### Changed
- Browser Observability is part of the runtime contract for browser-controller providers.
- Z.ai publishes safe browser/backend lifecycle metadata alongside verified model evidence.
- Documentation index was rewritten cleanly to expose the observability guide as a canonical document.

### Fixed
- Z.ai snapshot reads use bounded observation-only retry across execution-context replacement/navigation races; the upstream submit is never replayed.

### Evidence
- Deterministic regression suite: 62/62 PASS.
- `git diff --check`: PASS.
- Z.ai Browser Observability E2 was not treated as E3 reliability evidence.
- Qwen completion was not retried while guest/quota/auth state was unresolved.
- No E3 reliability claim is made.

## 0.6.1 - 2026-09-10

### Added
- Shared Browser Observability layer in `core/browser_observability.py`.
- Fail-closed model-evidence validation across requested/default model, UI/frontend selection, observed backend request model, and response model.
- Safe browser/backend lifecycle metadata for Qwen and Z.ai without recording cookies, tokens, signatures, CAPTCHA proof, or raw request bodies.
- `docs/BROWSER_OBSERVABILITY.md` as the canonical browser/runtime drift and observability guide.

### Fixed
- Z.ai observation now tolerates bounded execution-context/navigation races after submit without replaying the request.
- Z.ai runtime stores are re-bootstrapped after provider navigation before response polling continues.

### Evidence
- Deterministic regression suite: 62/62 PASS.
- `git diff --check`: PASS.
- Windows service restart: PASS.
- Controlled Z.ai strict browser-observability E2: NOT PASSED yet; latest live check returned `Z.ai first-event timeout` after submit. Prior GLM-5.3 default-routing E2 remains recorded separately, but no new stricter E2 pass is claimed in 0.6.2.
- Qwen was not re-tested for completion because the current guest session is already provider-rate-limited for the day; previous model-routing evidence is retained without unnecessary retry.
- No E3 reliability claim is made.

## 0.6.0 - 2026-09-10

### Added
- Dynamic provider model catalogs for Qwen Web and Z.ai Web. `/v1/models` now exposes provider-discovered namespaced ids instead of a small manually curated alias set.
- Configurable `default_upstream_model` policy for each Web provider. Current defaults are `qwen3.8-max` for `qwen-web` and `glm-5.3` for `zai-web`.
- Exact namespaced routing with provider-side catalog validation: `qwen:<upstream-id>` and `zai:<upstream-id>`.
- Safe backend model provenance diagnostics that record model ids only and do not retain tokens, cookies, signatures or CAPTCHA proof.

### Fixed
- Z.ai response polling now re-bootstraps runtime stores after provider navigation changes the page execution context.
- Browser-controller `backend_request_model` is no longer synthesized from the requested/default model when no backend request was observed.
- Qwen empty assistant completions caused by provider errors are no longer accepted as successful responses; current guest-quota exhaustion is classified as `rate_limit`.

### Evidence
- Deterministic regression suite: 58/58 PASS.
- `git diff --check`: PASS.
- Windows service restart: PASS; `HooshkaWebGateway` remained Running.
- Live `/v1/models`: 20 routable ids in the current session: 16 Z.ai, 3 Qwen, 1 ChatGPT Web.
- Z.ai generic-default E2: PASS with `zai-web -> glm-5.3`, selector `GLM-5.3`, backend request `glm-5.3`, and exact completion `ZAI_DEFAULT_MODEL_OK`.
- Qwen generic-default routing evidence: `qwen-web -> qwen3.8-max` reached the actual backend request and frontend selection. Completion is currently blocked by the provider's daily guest quota (`RateLimited`); no further live Qwen completion retries are claimed in this window.
- No E3 reliability claim is made.

## 0.5.1 - 2026-09-10

### Documentation
- Added canonical technical and practical documentation set: Start Here, current architecture, API reference, configuration reference, operations runbook, provider guide, security/governance guide, Hooshka integration guide, development guide, current troubleshooting guide, and practical usage recipes.
- Replaced the root README and documentation index with current multi-provider 0.5.x guidance.
- Updated Swagger metadata to the current product identity/version.
- Historical research/evidence documents remain preserved and explicitly separated from canonical current documentation.

### Evidence
- Documentation file-presence gate added to the release workflow for this update.
- Deterministic regression suite remains 54/54 PASS.
- No provider capability claim was expanded by this documentation release.

## 0.5.0 - 2026-09-10

### Project identity
- Canonical product name is **Hooshka Web Gateway** (`hooshka-web-gateway`).
- Hooshka module id is `web_gateway`.
- Local repository path migrated to `D:\Code\hooshka-web-gateway`.
- GitHub repository migrated to `khosravimm/hooshka-web-gateway`.
- Windows service migrated from legacy `WebLLMBridge` to `HooshkaWebGateway`.
- Runtime labels use the canonical `HWG-` prefix.

### Evidence
- Deterministic suite: 54/54 PASS.
- `/health`, `/ready`, `/modes`, and `/v1/models`: PASS after migration.
- Post-migration exact smoke: ChatGPT Web PASS, Qwen Web PASS, Z.ai Web PASS.
- DeepSeek Web remains blocked by current account state; no bypass attempted.
- Rollback ref: `rollback/pre-hooshka-web-gateway-migration`.
- No E3 reliability claim is made.

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
