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
