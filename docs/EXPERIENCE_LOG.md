# Experience Log

Append-only dated engineering observations. Stable conclusions are promoted to `LESSONS_LEARNED.md` or architecture docs.

## 2026-09-10 — Operational remediation and AWA reuse

- Initial Windows service state was misleading: SCM reported `Running`, while authenticated API requests failed with 500 because governance treated a legacy string identity as a dict.
- A tracked runtime credential was found in `config.yaml`. The current tracked file was sanitized; a new local runtime credential was provisioned outside Git rather than reusing or exposing the old value.
- Binding was reduced from `0.0.0.0` to `127.0.0.1` for the local gateway baseline.
- `/health`, `/ready`, and `/health/deep` were separated so process liveness and provider runtime readiness are distinguishable.
- The repository test suite initially failed during collection because `requests` was missing from declared dependencies. Dependency closure restored reproducible tests.
- ChatGPT Web tool capability was initially overstated: tools were advertised while only the final user message was sent to the Web UI. Full transcript/tools/tool_choice/tool-result serialization was added.
- Kilo/agent-style tool messages require an atomic protocol turn. Splitting the manifest/history across multiple web submissions creates a race in which ChatGPT can answer before seeing the full tool contract.
- Character-by-character prompt entry was unnecessarily slow for large agent manifests. `fill()` is now the primary composer input path with sequential typing only as fallback.
- ChatGPT transient `Thinking` text was once returned as the final API response. DOM completion detection now waits for a stable completed response and recreates locators each poll to survive React node replacement.
- Live tool behavior remained non-deterministic even after correct transport: ChatGPT sometimes emitted a tool envelope and sometimes pretended the command had already run.
- A strict JSON machine envelope plus bounded repair improved `tool_choice=required`, but broad auto-review remained unsafe.
- AWA (`D:\Code\ai-web-adapter`) was audited. Its historical live-E2 record showed that retrying every auto turn without a parsed tool call over-fired, created spurious tool calls, and risked loops. The broad-review idea in this repository was replaced with strong-signal-only review.
- Strong signals currently include explicit user request naming an offered tool, response mention of a tool, sandbox/internal-tool substitution markers, and observed English/Persian false-refusal patterns.
- Independent live validation after adopting the AWA rule: explicit bash request -> tool call; plain 2+2 -> direct final `4`; WSL local-state request -> bash tool call.
- AWA ADR-021 commitment-aware attempt logic was adapted: after submission begins, failures are ambiguous and are not automatically replayed. Regression tests verify post-submit one-attempt behavior and pre-submit bounded retry.
- AWA ADR-023 provider-local transport selection exposed a future multi-provider bug: an empty `supported_models` list acted as a wildcard. Routing is now exact/fail-closed and unknown provider/model returns 400 instead of silently crossing providers.
- AWA streaming architecture review exposed another hidden buffer: the Flask HTTP layer collected all async chunks before yielding. It now bridges async provider chunks to synchronous WSGI using an incremental queue.
- ChatGPT DOM remains buffered compatibility streaming despite the HTTP-layer fix. Live tool-stream evidence produced one tool-call data frame followed by `[DONE]`, with first data after ~33 seconds.
- Full live ChatGPT tool round-trip passed: model emitted bash call for `Write-Output ROUNDTRIP_OK`; supplied tool result was returned to Web Chat; second turn finished `stop`, zero repeated tools, final `ROUNDTRIP_OK`.
- Flask development server was replaced by Waitress 3.0.2 for the Windows service. Runtime log now reports `Serving on http://127.0.0.1:5000`.
- Historical restarts logged `Task was destroyed but it is pending!` for Playwright connection tasks. Provider close-before-event-loop-stop was added. After a live request and restart at 18:22:50 local, no new pending-task destruction line appeared in the inspected new log range.
- AWA itself is not treated as a drop-in verified dependency: its current `npm test` run during this audit failed a fail-closed unsafe-HOST regression. Historical findings were reused only as design evidence and then independently tested here.
- Version 0.3.0 establishes the operational ChatGPT Web / unified-gateway foundation. It is not the final four-provider release and is not E3.

## 2026-09-10 — D:\Tools research-bank experience mining

- The local research bank contains 89 top-level folders, 87 Git repositories, and 80 unique GitHub repositories after de-duplicating repeated remotes.
- Live GitHub metadata was collected for all 80 unique repositories. Release-asset download counts were additionally collected for 60 priority repositories. GitHub release-asset downloads are not equivalent to total installs/downloads and are treated as a separate signal.
- Deep source inspection prioritized Web-to-API/backend-heavy projects rather than popularity alone. Primary references included qwen2API, ds-free-api, FreeLLMAPI, WebAI-to-API, AIClient-2-API, grok2api, FreeQwenApi, gemini-web2api, and OmniRoute.
- A stable transport preference emerged across multiple independent implementations: direct backend HTTP/SSE/WebSocket first; browser-context fetch/XHR second when browser-bound session state is required; network interception third for discovery/capture; DOM submission/read only as the final inference fallback.
- qwen2API exposes a concrete backend-first Qwen flow around `/api/v2/chats/new`, `/api/v2/chat/completions?chat_id=...`, `/api/models`, `/api/v2/user/info`, chat cleanup and file/task endpoints. It also separates response-header, first-event and idle stream deadlines and detects errors embedded in HTTP-200 SSE.
- qwen2API and ds-free-api independently reinforce that tool-call output is a multi-dialect normalization problem. QNML/XML/JSON/token dialects can be malformed by Unicode/full-width/zero-width corruption and should be canonicalized before schema-gated parsing.
- FreeLLMAPI contains regression tests for Kimi/DeepSeek token syntax, Groq/Llama function tags, Qwen/Hermes XML and bare/fenced JSON. A crucial invariant is that an empty declared tool set means no tool is callable; detected-but-unparseable tool syntax is a protocol failure, not ordinary prose.
- ds-free-api demonstrates bounded incremental tool parsing, fuzzy/full-width marker normalization, parser memory limits and keepalive behavior while ambiguous tool syntax is withheld from the client.
- WebAI-to-API demonstrates a request-scoped browser state object, page/session leases, phase-specific timeouts, bounded observer queues, page poison/invalidation, explicit submission confirmation and provider-specific hooks. These are preferred patterns for future DOM fallback transports.
- AIClient-2-API treats OpenAI Responses as a first-class outward protocol with dedicated conversion of instructions, input items, output token fields, tools and streaming state. This supports implementing `/v1/responses` above provider transport rather than inside each provider.
- grok2api separates account-local failures from provider-wide failures, caps equivalent failure fingerprints, and treats errors that occur after downstream HTTP 2xx as stream failures requiring separate finalization/audit.
- FreeQwenApi demonstrates an important intermediate transport: use the logged-in browser to bootstrap session/token state and execute same-origin backend `fetch()` calls without depending on DOM chat controls.
- gemini-web2api demonstrates provider-specific runtime discovery of volatile backend build identifiers and isolation of positional/RPC-style web payloads from the outward API schema.
- OmniRoute demonstrates that anti-bot clearance, User-Agent/client hints, TLS/JA3 and IP/proxy can form one coupled fingerprint bundle. It also tests origin + normalized-path scoping before injecting provider credentials, preventing same-prefix/suffix-spoof leakage.
- The resulting architectural policy is documented in `BACKEND_FIRST_PLAYBOOK.md`; detailed provenance and project-by-project transfer decisions are in `TOOL_BANK_EXPERIENCE_MINING_2026-09-10.md`.

## 2026-09-10 — Qwen backend-first implementation

- Live Qwen network research observed frontend version `0.2.91`, `/api/v1/auths/`, `/api/v2/models/`, `/api/v2/chats/new`, and SSE completion on `/api/v2/chat/completions?chat_id=...`.
- Raw same-origin `fetch()` for chat creation encountered Alibaba/BX/WAF challenge behavior. The bridge therefore did not declare direct HTTP or raw browser-fetch operational.
- Qwen's current frontend exports its chat controller from the dynamically discovered `main.js`. Calling `openNewChat()` and `beforeSendMessage()` invokes the normal backend/session/anti-bot path without typing or clicking the DOM.
- A dedicated headless Chrome profile under ignored runtime state successfully completed real guest-mode Qwen chats even while `/api/v1/auths/` returned 401. This avoids copying credentials from the user's personal browser profile.
- The controller-backed provider passed direct provider E2 and gateway E2 for non-stream and stream paths. The outward stream is classified `reconstructed` because bridge deltas are derived from controller in-memory message state even though the Qwen frontend itself receives native SSE.
- Initial implementation accepted `thinking/search` parameters but did not change frontend feature state. Source/runtime inspection found Qwen's exported feature manager and its `selectFeature`, `deselectFeature`, and `setThinkingMode` methods; the transport now uses those official frontend APIs instead of DOM controls.
- Thinking on/off passed E2 after that correction. A search-enabled request also completed, but search remains unadvertised pending independent evidence that a search phase/event actually occurred.
- Qwen tool support remains fail-closed (`tools=false`) until tool dialect, multiple calls, malformed dialect, empty allowlist, and full round-trip are independently E2-tested.
