# Changelog

All notable changes to mcp-web-bridge are recorded here.

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
