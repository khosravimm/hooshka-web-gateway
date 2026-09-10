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

## Reuse sources

- DeepSeek Web PoC: observed model dialect variability, DSML normalization, reasoning/content/tool boundary issues, lifecycle and real tool-call E2E testing.
- AWA (`D:\Code\ai-web-adapter`): commitment-aware attempts, strong-signal-only tool retry, provider-local transport selection, incremental streaming boundaries, origin/session security, config precedence, observability minimization, and Responses/tool-round-trip experience.

Every reused lesson must be independently validated in this repository before being treated as implementation evidence.
