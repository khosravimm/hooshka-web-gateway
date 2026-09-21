## 1.0.0-dev.5 - 2026-09-21 - WIP (assisted discovery and governed interaction)
- Added governed Browser Behavior Lab for bounded hover/focus and explicitly approved non-destructive click observations.
- Behavior evidence captures target before/after state plus bounded network/WebSocket/SSE metadata; send/submit/destructive/auth-exit/payment-like clicks fail closed.
- Added approval-gated AI-assisted Discovery. Deterministic probes remain first; AI output is recorded only as E0/CANDIDATE and cannot directly mutate Profile/Account or certify capability.
- Added policy-based Discovery AI Router with ordered/least-loaded/weighted-load selection, health/capability/cooldown filtering, strict exact routing and no bypass of provider limits/challenges.
- Work Register upgraded to v1.3.0 with HWG-WORK-018..021 for AI assistance, routing, Browser Behavior Lab and target-provider self-use transport qualification.
- Added fail-closed target-provider self-use gate: explicit user approval is necessary but insufficient; deterministic send/receive/completion paths plus a successful controlled nonce round-trip must be qualified against the current transport fingerprint.
- Added versioned Provider Self-Use Transport Qualification schema and guarded human-test action in the Discovery Control Plane.

### Evidence
- Targeted self-use/assisted-discovery/routing/governance tests: 31 passed before final release validation.
- Live read-only DeepSeek hover probe observed DeepThink before/after with unchanged pressed state and 4 network requests; no click or prompt was sent.
- E2/E3 certification remains open; dev.5 is an in-development baseline, not an RC.

## 1.0.0-dev.4 - 2026-09-21 - WIP (governed operational model)
- Registered HWG-MISSION-NG-001 and HWG-KT-WEBCHAT-001 as normative governance sources in the canonical repository.
- Added requirement traceability with explicit IMPLEMENTED/PARTIAL/OPEN/CONFLICT semantics and E0-E3 separation.
- Reworked Control Plane navigation and runtime/provider/profile responsibilities around operational dependency order instead of duplicated technical controls.
- Fixed Desktop Runtime Agent contract drift: config-owned port, health endpoint and interactive Scheduled Task installation path.
- Added versioned machine-readable Provider Profile v1 and Account Instance v1 JSON Schemas as the first NG contract baseline.
- Added read-only legacy-config projection and `/panel/api/ng/inventory`; current config projects to 4 profiles + 4 accounts and reports shared-profile isolation as a machine-readable conflict.
- Synchronized application, manifest and Control Plane UI version to 1.0.0-dev.4 and added a regression gate for future version/history drift.
- Rebuilt Discovery as a governed pipeline with versioned Recipe/Result contracts, explicit lifecycle, Update Candidate review, Evidence promotion boundaries and reconstruction records; the former scanner is retained only as an Exploration probe.
- Added a dedicated `کاوش و گواهی` Control Plane workspace plus governed Discovery Run creation/listing; every new run starts at `RESEARCH_REQUIRED` and persists under `.runtime-dev/discovery/`.
- Connected the Discovery workflow to read-only Baseline/Exploration, explicit Update Candidate review (`ACCEPT/HOLD/REJECT`) and Interactive Certification; E2 PASS requires both an evidence record and explicit user confirmation.
- Hardened generic frontend discovery to include visible `[role=button]` and keyboard-focusable `[tabindex="0"]` surfaces; live DeepSeek observation now discovers composer, DeepThink and Search without provider-specific selector patches.
- Added `HWG-WORK-REGISTER-001` as the machine-readable remaining-work/anti-forgetting register with dependencies, target versions, evidence requirements and exit criteria; DONE items are invalid without evidence and completion time.
- Exposed the Work Register through `/panel/api/governance/work-register` and a dedicated Control Plane workspace so open P0/P1 work is visible from the product itself.

### Evidence
- Deterministic suite after governed live-read-only Discovery workflow and anti-forgetting hardening: 267 passed.
- Live read-only DeepSeek discovery observed the composer, DeepThink and Search controls plus 7 candidate backend endpoints; no prompt was submitted and no control state was changed.
- `HWG-WORK-017` (frontend/accessibility probe robustness) closed with recorded E1 + live-read-only evidence; `HWG-WORK-001` remains IN_PROGRESS pending scoped interactive E2 certification.
- Live development runtime: Desktop Runtime Agent reachable on configured port 5181; DeepSeek runtime start completed successfully.
- Production/legacy port 5000 was not modified by this development change set.
- No E3 reliability claim is made.

## 1.0.0-dev.2 - 2026-09-20 - WIP (shared browser + SDK + spec)
- Added `core/browser_pool.py` (SharedBrowserPool: one Chrome, isolated tab
  per provider/account, focus-guard enforced, opt-in via
  `runtime_orchestration.shared_browser`) + ADR-002 + `tests/test_browser_pool.py`.
- Added reference Python SDK `sdk/python/hwg_client.py` (models/chat/stream/
  responses/providers/capabilities, `requests`-only) + `tests/test_sdk_client.py`.
- Added reference TypeScript SDK `sdk/typescript/` (zero-dep `fetch` mirror of
  the Python client; SSE streaming, typed `HwgError`); typecheck clean,
  live smoke 6/6 vs 5080 (models EOF, providers, capabilities, error envelope,
  chatgpt-web stream, responses).
- ADR-002 pilot: `ChatGPTWebProvider.bind_shared_pool()` (opt-in tab binding,
  legacy fallback) + factory wiring in `main.py` (disabled by default) +
  `tests/test_shared_pool_pilot.py`.
- Discovery engine (`core/discovery_engine.py` + `core/control_discovery.py` +
  `core/feature_controls.py`): read-only frontend/backend capability discovery
  with evidence ladder (E0/E1/E2) and drift diff; versioned profiles under
  `docs/profiles/<id>/`; `scripts/discover_provider.py` onboards known or NEW
  webchats via CDP. Live z.ai run: model selector (E1) + 10 backend endpoints
  + search icon flagged unclassified for hover probing.
- Control checklist HWG-CTRL-REQ-001 v1.0.0 adopted (`docs/`); full 273-control
  compliance matrix (`docs/evidence/HWG_CTRL_COMPLIANCE_20260920.md`):
  ~91 pass / ~106 partial / ~75 open. Release verdict: NOT READY (open ★ blockers).
- Single-window migration live (ADR-003): ONE Chrome CDP 9330 + shared profile;
  3 providers verified through it (S1 exact each); per-origin isolation measured;
  backups in `.runtime-dev-backup-20260920/`; rollback documented.
- Session validation per provider (`GET /panel/api/providers/<id>/session`,
  read-only, no focus steal) + explicit logout (`POST .../logout` with confirm,
  CDP site-data clear + audit); `validate_session()` on all 3 adapters.
  Live: chatgpt/zai/deepseek all authenticated+composer_ready.
- API keys are verify-only hashes: `core/key_hash.py`, AuthManager hashes on
  add/load/verify (existing tests green); panel stores hash only, audit logs
  key_ref+suffix (plaintext secret never persisted/logged). Live lifecycle
  verified: create → hash-only config → list → delete.
- Live logout verified end-to-end on deepseek-web (`docs/evidence/
  HWG_LOGOUT_LIVE_20260920.md`): CDP `Storage.clearDataForOrigin` wiped origin
  cookies (16→0) + localStorage (21→0), audit `provider_logout` recorded
  (key_ref only, no secrets), read-only session check flipped to
  `authenticated=false / login signal` with zero side effects. The shared
  single-window session is now logged out on deepseek (owner re-login needed,
  opened via the panel "Open Browser" button).
- Z.ai Web disabled in `config.yaml` (`enabled:false`) per owner decision;
  canonical runtime now serves chatgpt-web + deepseek-web only. Both live S1
  probes pass (15s / 12s exact), session endpoints report authenticated +
  composer_ready, and the shared single-window browser remains on CDP 9330.
- Verification: 231 pytest tests pass, panel E2E 5/5 pass, TypeScript SDK
  smoke 6/6 pass (models/providers/capabilities/error/stream/responses).
- New Agent API spec `docs/HWG_1.0_AGENT_API_SPEC_v1.0.0-dev.1.md`
  (supersedes dev.0: documents `POST /v1/responses`).

### Verified
- **231 tests pass** (225 + 6 session/key-security).
- Live panel E2E 5/5 on port 5080 (shell fa/RTL + models/providers/capabilities).

## 1.0.0-dev.1 - 2026-09-20 - WIP (consolidation from hwg-next-0.9.3)
- Base decision: `hwg-next-1.0.0` is the canonical line (Flask, config-driven
  4 providers, Persian control panel, service orchestration, agent API spec).
- Ported pure-logic modules from `hwg-next-0.9.3` (no new dependencies):
  `core/unicode_norm.py` (fullwidth→ASCII before tool parsing, wired into
  `parse_tool_calls`), `core/tool_allowlist.py` (empty allowlist never a
  wildcard; unknown names rejected), `core/tool_adapter.py` (standard→native
  mapping with structured `unsupported_tool` error), `core/commitment.py`
  (NOT_SENT→MAYBE_SENT→COMMITTED→TERMINAL, retry only before send),
  `core/focus_guard.py` (background never foregrounds; only
  `user_initiated()` allows).
- Added `tests/test_consolidated_093.py` (7 tests).
- Added `POST /v1/responses` (normalized onto chat pipeline; streaming
  explicitly 404/400 fail-closed) + `tests/test_responses_api.py` (4 tests).

### Verified
- **203 tests pass** — 192 pre-existing + 7 consolidation + 4 responses.
  Live: `/v1/responses` streaming→400, panel E2E 5/5 on port 5080.
- hwg-next-0.9.3 suite still green: 47 passed (donor line, frozen).

## 1.0.0-dev.0 - 2026-09-20 - WIP (new development line)
- Project bootstrapped at `D:\Code\hwg-next\hwg-next-1.0.0` from the operational
  `hooshka-web-gateway` v0.7.29 seed (adapters/core/runtime/tools/tests/docs copied;
  `.venv/.runtime/logs/.env` excluded).
- Isolated development configuration: new server port **5080**, dedicated dev CDP
  ports `9323/9324/9325/9326`, profiles under `.runtime-dev`, dev orchestration
  service/task names (production service on port 5000 untouched).
- Registered owner requirements + mission + knowledge-transfer requirements as the
  versioned register (moved into `docs/requirements/`).
- Added `HWG_1.0_AGENT_API_SPEC_v1.0.0-dev.0` — the standard, OpenAI-compatible
  agent API contract for HWG (target of the owner goal: agents such as the VS Code
  kilo extension consume HWG through this API).
- Goal: one standard API for Web-chat providers so external agents use standard
  tools; provider-specific browser/session/transport stays isolated.

### Verified
- WU-AP-001 E1 (local, no provider): app load + smoke `/health /ready /v1/models
  /panel/` all 200; 110 unit tests pass (0.88s). Evidence:
  `docs/evidence/HWG_WU_AP_001_E1_EVIDENCE_20260920.md`.
- WU-AP-002 (contract validation) + WU-AP-003 (endpoints): unknown
  model/provider now `404` with codes `model_not_found`/`unknown_provider`
  (was 400); added `GET /v1/providers` and `GET /v1/capabilities` (versioned
  manifest with `compatibility_baseline: openai-2026-09-20` + access policy);
  spec §3/§9 updated; 6 new contract tests; **116 tests pass (0.80s)**. Evidence:
  `docs/evidence/HWG_WU_AP_002_003_CONTRACT_20260920.md`.

## 0.7.29 - 2026-09-18
- Removed hard-coded provider/runtime inventory from restart orchestration, desktop runtime agent, service manager, and control-panel runtime actions.
- Added canonical `runtime` metadata per provider plus `runtime_orchestration` settings in `config.yaml`; provider IDs, count, CDP ports, profiles, home URLs, service/task names, and desktop-agent endpoint are now configuration-driven.
- Normal Restart-All operates only on enabled provider runtimes from config; explicit Repair-All may include disabled runtimes for diagnostic recovery.
- Added config validation for duplicate provider IDs/CDP ports and required Chrome CDP runtime fields.
## 0.7.28 - 2026-09-18
- Fixed Control Panel Service Restart self-termination: gateway restart is now executed by an independent SYSTEM Scheduled Task instead of synchronously from inside the HooshkaWebGateway service process.
- Added restart request/state tracking for the Service Restart action and UI recovery polling until gateway health is restored.
- Service Restart intentionally preserves provider CDP/browser runtimes; it restarts only HooshkaWebGateway. Configuration-triggered Restart-All remains a separate orchestration path and may restart provider runtimes.
- Validated real restart lifecycle through Running -> StopPending -> StartPending -> Running with final `/health` status `ok`.

## 0.7.27 - 2026-09-17
- Fixed Control Panel Open Browser false-positive: success now requires a real visible top-level Chrome window in the interactive user session for the provider profile.
- Added controlled runtime restart fallback when Chrome profile singleton/background state absorbs `--new-window` without surfacing a desktop window.
- Ready Providers now counts only enabled providers; disabled providers remain manually inspectable via Open Browser.

## 0.7.26 - 2026-09-17

- Provider Open Browser no longer depends on the enabled provider registry; all four configured providers can be opened for login/CAPTCHA/restriction inspection even when a provider is disabled for routing.
- Open Browser resolves CDP from canonical config and keeps Desktop Runtime Agent as the primary interactive launcher with CDP as fallback.

## 0.7.25 - 2026-09-17

- Fixed restart-state persistence bug caused by PowerShell case-insensitive collision between the state-file variable and the state function parameter.
- Restart-all now tolerates slow provider restart calls and determines final success from gateway health plus bounded readiness of all four dedicated CDP runtimes, rather than treating an intermediate provider-call timeout as a permanent failure.
- Provider restart timeout increased and final CDP readiness is polled before completion is recorded.

## 0.7.24 - 2026-09-17

- Restart-all orchestration moved to an independent SYSTEM Scheduled Task so configuration-triggered restarts survive termination/restart of the gateway process itself.
- Added restart request/state contract (`scheduled -> running -> completed/failed`) and `/panel/api/restart/status`; Config UI waits for the exact restart request to finish instead of inferring recovery from a transient health response.
- Restart completion now requires gateway health plus all four dedicated provider CDP ports ready.

## 0.7.23 - 2026-09-17

- Config Save Settings and raw YAML save now schedule a full HWG restart cycle: all four provider browser runtimes via the interactive Desktop Runtime Agent, then the Desktop Runtime Agent task, then the HooshkaWebGateway Windows service.
- Control Panel waits for gateway recovery after configuration saves and refreshes live state instead of only warning that a restart may be required.
- Windows service manager no longer launches interactive provider Chrome runtimes from LocalSystem/Session 0 during gateway start/restart; interactive runtimes are owned by the Desktop Runtime Agent in the logged-in user session.
- Continued hardening of Provider Open Browser and interactive runtime ownership.

## 0.7.22 - 2026-09-17

- Control Panel `Open Browser` now delegates to the Session-1 desktop runtime agent so provider Chrome windows become visibly available to the logged-in user; direct CDP target creation remains a fallback only.
- Provider action layout widened and normalized for readable `Open Browser`, `Restart CDP`, and `Test` controls.
- Canonical runtime remains `D:\Code\hooshka-web-gateway`; retired `mcp-web-bridge` is not accepted as a runtime source.

## 0.7.21 - 2026-09-16

### Action Orchestration
- Added Gateway-to-CAG Action Candidate bridge.
- Agentic Hooshka-context output that is stopped at the Gateway boundary now creates a CAG action candidate.
- Candidate metadata omits raw model output and held commands.
- Streaming Hooshka-context boundary also registers candidates after buffering and classification.

## 0.7.20 - 2026-09-16
### Fixed
- Added a Gateway-level Hooshka/CAG context boundary so CAG is defined as Hooshka Controlled Action Gateway, not Client Access Gateway.
- Added an agentic response boundary that prevents executable shell/code snippets and Copy/Download artifacts from leaving `/v1/chat/completions` as human chat content in Hooshka context.
- Streaming Hooshka-context responses are buffered at the Gateway boundary before safe-chat delivery to avoid partial command leakage.
### Validation
- Added unit tests for context injection, response boundary metadata, and no raw command leakage in message content or provider metadata.

# Changelog

All notable changes to Hooshka Web Gateway are recorded here. `mcp-web-bridge` is the legacy compatibility identity during migration.

## 0.7.19 - 2026-09-16

### Fixed
- Clarified Overview request metrics by separating gateway requests from model traffic.
- Added a Request Breakdown card so panel polling is not confused with model usage.
- Model accounting empty state now shows excluded panel/health/metadata request counts.
- Model accounting now reports `token capture unavailable` when requests are counted but token fields were not captured.

### Validation
- Deterministic tests verify request bucketing and dashboard labels.

## 0.7.18 - 2026-09-16

### Changed
- Compact large request and token counters in the model accounting panel using k/M/B suffixes while preserving full values in tooltips.

### Validation
- Deterministic tests verify compact number formatting and updated model accounting labels.

## 0.7.17 - 2026-09-16

### Changed
- Renamed the Overview model panel to `Model Traffic & Token Accounting (1h)`.
- Replaced ambiguous `req`, `Prompt`, `Completion`, and `Total` labels with `Requests`, `Input tokens`, `Output tokens`, and `Total tokens`.
- Made model accounting cards compact and side-by-side instead of large sparse vertical cards.
- Display token fields that were not captured as `not captured` instead of showing misleading zero values.

### Validation
- Added deterministic UI assertions for compact model accounting labels and removal of the ambiguous `req` badge.

## 0.7.16 - 2026-09-16

### Fixed
- Removed fabricated zero-request model-usage rows from the Control Panel; empty telemetry now states that no measured model traffic exists instead of presenting placeholders as statistics.
- Added estimated usage accounting for Web-chat responses that return zero upstream usage, marking estimates with `usage_estimated` metadata.
- Added prompt-token estimates for audit accounting so per-model dashboards can show request-side usage when Web-chat providers do not expose upstream billing data.
- Added field-level token availability so missing prompt/completion values are shown as unavailable rather than misleading zeroes.

### Validation
- Deterministic tests verify model usage no longer fabricates zero rows and zero-usage text responses receive explicit estimated usage metadata.

## 0.7.15 - 2026-09-16

### Fixed
- Model Usage now always shows every configured provider/default model, even when the last hour has zero model requests.
- Zero-request rows explicitly show `0 req` and token accounting as unavailable instead of rendering an empty/no-data box.

### Validation
- Headless render verifies four model usage rows are visible for the four configured Web Chat providers.

## 0.7.13 - 2026-09-16

### Changed
- Replaced the primary Config tab raw YAML editor with a Human Settings form for common server, CDP, auth, and provider defaults.
- Moved raw YAML editing into an Advanced Raw YAML expander.

### Added
- Added `/panel/api/config/summary`.

### Added
- Added Model Usage (1h) to the Overview tab, grouped by provider/model with request counts and prompt/completion/total token counters when audit data is available.
- Added `/panel/api/model_usage`.

### Validation
- Deterministic tests verify the model usage UI and backend endpoint wiring.

## 0.7.12 - 2026-09-16

### Changed
- Replaced raw JSON rendering in the Control Panel Service tab with user-facing service summary cards, state labels, action messages, and an optional raw service-manager output expander for debugging.

### Validation
- Headless render verifies the Service tab maps the service payload to UI fields instead of exposing JSON directly.

## 0.7.11 - 2026-09-16

### Fixed
- Reworked the Control Panel Service tab to read the canonical Windows service state from structured `Get-Service` and `Get-CimInstance` data instead of parsing formatted PowerShell table output.
- Service Management now reports the canonical `HooshkaWebGateway` service correctly and includes legacy `WebLLMBridge` status for migration visibility.
- Service action buttons are now state-aware and disabled when the action is not valid for the current service state.

### Validation
- Headless render verifies the Service tab shows `Running` for the installed canonical service using live `/panel/api/service/status`, not a stale initial snapshot.

## 0.7.10 - 2026-09-16

### Fixed
- Removed horizontal overflow from the Control Panel Providers table by using a fixed-layout table, explicit column widths, reduced provider-cell padding, breakable runtime URLs, and wrapped capability badges.
- Scoped the layout changes to the Providers table so Sessions and API Keys tables keep their existing behavior.

### Validation
- Headless render verifies the Providers table has no horizontal overflow at the user-observed viewport width.

## 0.7.9 - 2026-09-16

### Fixed
- Replaced the Control Panel Default Model `input+datalist` with a real `<select>` control so all selectable upstream model options are visible and reliably selectable.
- Added a visible current-model line under each provider model selector.
- Wrapped provider capability badges into multiple lines to reduce horizontal table overflow.

### Validation
- Headless Control Panel render verifies Qwen and Z.ai model selectors expose multiple concrete options.

## 0.7.8 - 2026-09-16

### Fixed
- Split the Waitress HTTP worker pool from the bounded provider worker pool.
- Replaced hardcoded `threads=4` with configurable `server.threads` and `HOOSHKA_GW_HTTP_THREADS`, defaulting to 12 HTTP workers.
- Kept provider concurrency separately bounded by `server.provider_concurrency` / `HOOSHKA_GW_PROVIDER_CONCURRENCY` so browser-backed Web Chat work cannot starve fast endpoints.

### Validation
- Regression test covers configurable HTTP workers and separate provider pool configuration.
- Operational probes showed `/health`, `/ready`, and `/v1/models` staying responsive while provider inflight remained zero.

## 0.7.7 - 2026-09-16

### Fixed
- Improved the native Control Panel request chart with dynamic Y-axis scaling, grid ticks, X-axis time labels, better padding, max annotation, and clearer empty-state rendering.
- Changed `/panel/api/stats` to emit a continuous 60-minute series, including zero-count minutes, so the X-axis preserves real time gaps.
- Reduced visual clutter by thinning zero-value point markers for dense request windows.

### Validation
- Control Panel chart remains self-contained with no external CDN dependency.

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

