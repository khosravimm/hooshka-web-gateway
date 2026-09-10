# Lessons Learned

This document records stable engineering lessons that should survive individual incidents and chat sessions.

## 2026-09-10 — ChatGPT Web operationalization

1. **Process running is not readiness.** A Windows service can be `Running` while every authenticated API request fails. Liveness, readiness, and deep-health are separate operational contracts.
2. **Secrets must not live in tracked config.** Runtime API credentials belong in an ignored/runtime secret source or service environment, not in Git history.
3. **OpenAI-compatible JSON shape is not Agent compatibility.** Agent clients exercise system messages, tools, tool_choice, assistant tool_calls, tool results, streaming, and multi-turn continuation. Those paths need independent tests.
4. **Web-model tool behavior is non-deterministic.** The gateway must make transport/normalization deterministic while acknowledging model planning variability.
5. **Do not broadly retry every no-tool final in auto mode.** AWA live experience proved this can convert legitimate final answers into spurious tool calls and risk non-terminating loops. Retry/review only on strong signals.
6. **Commitment boundary controls retry safety.** Before submission a retry may be safe. Once submission starts, replay is ambiguous and must fail closed unless an idempotency/reconciliation mechanism proves safety.
7. **Transient UI text is not completion.** ChatGPT may expose `Thinking` or partially reconciled DOM nodes. Completion detection must use stable response state and recreate locators because React can replace nodes during generation.
8. **Agent protocol envelopes must be atomic.** Splitting tool manifests/history into multiple submitted web-chat messages lets the model answer before receiving the full contract.
9. **HTTP streaming must not re-buffer.** Even if a provider is incremental, a server layer can accidentally collect all chunks before yielding. Streaming correctness must be tested end-to-end.
10. **Streaming provenance must be truthful.** ChatGPT DOM currently provides buffered compatibility streaming, not native token streaming. Future providers may have native or reconstructed transports; advertise the distinction.
11. **Routing must fail closed.** In a multi-provider gateway, an unknown model/provider must never silently route to another provider. Model resolution is exact; transport fallback stays inside the selected provider.
12. **Provider capability claims need evidence.** Do not advertise arbitrary upstream model names just because a web UI can select models. Use canonical gateway model IDs until provider-specific model selection is proven.
13. **Browser/session state is a security boundary.** AWA's origin/session work shows future providers need explicit origin allowlists, isolated account/profile state, and exclusive ownership of browser profile/session resources.
14. **Observability should allowlist metadata, not redact arbitrary content after logging.** Prompt text, reasoning, tool arguments/results, credentials and citation URLs may be sensitive; evidence should store bounded metadata unless content capture is explicitly required.
15. **A current test failure in a source project does not invalidate all historical lessons, but it prevents treating that project as a drop-in verified implementation.** AWA's current `npm test` had a fail-closed HOST regression failure during this review, so concepts were reused and independently re-tested rather than copied blindly.
16. **Backend-first should be an enforced transport hierarchy, not an informal preference.** Prefer direct backend HTTP/SSE/WebSocket; then browser-context fetch/XHR when session state is browser-bound; then network interception for discovery; use DOM inference only as the final fallback.
17. **A web stream needs phase-specific deadlines.** Connection/headers, first parsed event, meaningful-event idle time, and total lifetime are different failure modes. Arbitrary received bytes should not reset the meaningful-event idle timer.
18. **HTTP 200 does not prove stream success.** Several Web-to-API implementations inspect SSE payloads for provider errors after headers have already committed successfully; the common stream state machine must support failed/partial terminal states after downstream 2xx.
19. **Tool normalization belongs above individual provider transports.** Model/provider failover can carry forward a previous model's private tool syntax. A shared normalization layer must handle multiple dialects, Unicode/markup corruption, schema gating, argument validation/coercion, deduplication and bounded buffering.
20. **An empty declared tool set means no callable functions.** Never treat an empty allowlist as a wildcard. Bare JSON or tool-looking text must remain ordinary output unless it names a tool explicitly declared by the current request.
21. **Detected-but-unparseable tool syntax is not a successful final answer.** It is a protocol ambiguity requiring a bounded repair or explicit failure; raw dialect text must not leak through as if agent execution completed normally.
22. **Browser state can be useful without DOM inference.** A logged-in browser may serve as the session/bootstrap and same-origin execution environment for backend `fetch`/XHR, preserving browser-bound cookies/fingerprint while avoiding fragile UI automation.
23. **Anti-bot state is often a coupled fingerprint bundle.** Clearance cookies, User-Agent/client hints, TLS/JA3 behavior and IP/proxy affinity may need to remain consistent. Version the bundle and invalidate cached challenge/session artifacts when the fingerprint changes.
24. **Credential injection must be origin-and-path scoped after URL normalization.** Naive string-prefix matching can leak provider credentials to spoofed/similar destinations. Provider-owned upstream credentials should replace untrusted caller Authorization only on routes owned by that provider.
25. **Retry policy must distinguish account-local from provider-wide failures.** Repeating the same provider-wide stream-idle failure across every account multiplies latency without improving success. Use bounded retry budgets and equivalent-failure fingerprints.
26. **Volatile Web-backend identifiers need runtime discovery.** Build IDs, frontend versions and similar RPC parameters should be isolated in provider-specific discovery/refresh logic rather than hard-coded into the gateway contract.
27. **OpenAI Responses is a protocol layer, not merely another endpoint alias.** Instructions, typed input items, function-call items, parallel tools and stream event sequencing require explicit conversion above the provider transport.
28. **A frontend controller can be a backend transport without becoming DOM automation.** When anti-bot/session logic is encapsulated by the official Web frontend, invoking its controller APIs inside an isolated browser context preserves backend-first semantics better than typing/clicking UI controls.
29. **Do not copy a user's whole browser storage to bootstrap a provider.** Browser storage can contain unrelated-site credentials. Prefer an isolated provider profile or an explicitly scoped session mechanism; Qwen guest mode proved sufficient for the current basic-chat path.
30. **A request flag is not evidence that a Web feature was activated.** Parameters such as thinking/search must be traced to the provider's actual feature state or payload. Capability advertisement stays off until that mapping is independently demonstrated.
31. **HTTP 200 is not a stream-success signal.** A Web backend may return an application-level terminal error as JSON with status 200. Content type and application envelope must be classified before the SSE state machine starts.
32. **Account-local failure must not be promoted to provider-wide failure.** DeepSeek's live muted response is tied to the current account/session state; retrying every account or declaring the provider down would be incorrect without equivalent failure evidence.
33. **Signature/captcha dependencies belong to the provider transport boundary.** Z.ai completion currently couples `X-Signature`, device/session context and CAPTCHA. Shared gateway code should classify the resulting challenge, while provider-specific code owns any legitimate bootstrap needed to satisfy it.

## Reuse sources

- DeepSeek Web PoC: observed model dialect variability, DSML normalization, reasoning/content/tool boundary issues, lifecycle and real tool-call E2E testing.
- AWA (`D:\Code\ai-web-adapter`): commitment-aware attempts, strong-signal-only tool retry, provider-local transport selection, incremental streaming boundaries, origin/session security, config precedence, observability minimization, and Responses/tool-round-trip experience.
- `D:\Tools` research bank: backend-first Web protocols, Qwen/DeepSeek/Gemini wire contracts, multi-dialect tool recovery, browser-context backend access, stream failure semantics, retry/failure fingerprinting, anti-bot fingerprint coupling, and multi-protocol gateway conversion. Detailed source provenance is recorded in `TOOL_BANK_EXPERIENCE_MINING_2026-09-10.md`.

Every reused lesson must be independently validated in this repository before being treated as implementation evidence.

34. **Separate navigational bootstrap from the commitment boundary.** A frontend controller may navigate while creating a conversation. Recovering or retrying that phase is safe only before the actual user-message submit; after submit, automatic replay remains forbidden.
35. **Dynamic frontend module loading needs bounded pre-submit resilience.** A discovered module URL can be correct while CDN import fails transiently. Retry the bootstrap dependency with a small budget, but never convert that into replay of a committed user turn.
36. **Use provider-native mode semantics, not invented booleans.** Qwen currently exposes `Auto`, `Thinking`, and `Fast`; wire-level validation showed that the non-thinking path is represented by `Fast`, not an invented `Disabled` mode.
