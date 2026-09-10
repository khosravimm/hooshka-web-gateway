# Unified Web Chat API Architecture

## Target
One local OpenAI-compatible API for authenticated Web Chat providers:

```text
Client / Kilo / SDK / Agent
           |
           v
 Unified OpenAI-Compatible API
           |
  Exact Provider/Model Router
   |        |       |       |
ChatGPT  DeepSeek  Qwen   Z.ai
  Web      Web      Web    Web
```

## Core invariants

1. **Exact fail-closed routing.** Canonical model ids resolve to exactly one provider. Unknown/ambiguous ids return an error; there is no implicit cross-provider fallback.
2. **Provider-local transport selection.** DOM/network/native-web-protocol choices are internal to one provider and must satisfy that provider's capability requirements before priority is considered.
3. **Truthful capability/provenance.** Streaming/tool/vision/search claims reflect observed behavior. Suggested provenance vocabulary: `native`, `reconstructed`, `buffered`, `emulated`.
4. **Unified normalized tool contract.** Provider-specific JSON/DSML/other observed dialects normalize to OpenAI `tool_calls`. Tool results return through the same conversation contract.
5. **Commitment-aware retries.** Retry is allowed only before browser/network submission has begun. Post-submit failure is ambiguous and is not automatically replayed.
6. **Atomic agent turns.** Tool manifests and transcript envelopes are submitted as one provider turn unless the provider has a proven native structured channel.
7. **Session isolation.** Provider/account browser state must be isolated. A profile/session resource has one runtime owner at a time.
8. **Loopback by default.** The service binds to `127.0.0.1` unless a separately reviewed remote-access design is introduced.
9. **Secrets outside Git.** Web sessions, cookies, tokens and local gateway API keys are runtime secrets; tracked config contains references/options only.
10. **Sanitized observability.** Evidence stores request/provider/model/attempt/phase/latency/error metadata by default, not raw prompts, reasoning, tool arguments/results or credentials.

## Canonical model namespace

Current implemented model:
- `chatgpt-web` -> ChatGPT Web provider

Planned canonical provider ids/models:
- `deepseek-web` plus explicitly proven DeepSeek behavior variants as model ids/aliases where needed;
- `qwen-web` plus model/mode ids only after UI/protocol discovery and E2 proof;
- `zai-web` plus model/mode ids only after UI/protocol discovery and E2 proof.

Provider/model aliases must be explicit registry entries. An empty supported-model list is not a wildcard.

## Provider adapter contract
Each provider should implement:
- `health_check()` — non-mutating runtime reachability;
- `list_models()` — only canonical/proven ids;
- `chat_completion()` — normalized non-stream response;
- `chat_completion_stream()` — honest stream semantics;
- `close()` — deterministic cleanup;
- provider-specific session/origin/runtime state;
- tool protocol adapter/normalizer if tools are supported.

## ChatGPT Web baseline
As of version 0.3.0:
- authenticated local gateway operational;
- exact canonical model `chatgpt-web`;
- basic chat E2 verified;
- JSON/observed DSML normalization;
- explicit/strong-signal auto tool routing;
- tool round-trip E2 verified;
- SSE tool-call compatibility verified;
- DOM stream provenance is `buffered`, not native;
- Windows service uses Waitress and loopback binding.

## DeepSeek integration strategy
Reuse the already validated `deepseek-api-kit-poc` protocol knowledge rather than reimplementing from memory:
- real web session creation;
- proof-of-work challenge;
- current completion payload;
- SSE snapshot/delta parser;
- thinking/search combinations;
- JSON + observed DSML compatibility lessons;
- no official DeepSeek API dependency.

The integration should become a first-class provider behind this gateway, not an HTTP cross-provider fallback hidden inside the ChatGPT adapter.

## Qwen / Z.ai onboarding sequence
For each new provider:
1. Baseline browser/session/account state without modification.
2. Confirm legal target origins and exact browser/session isolation requirements.
3. Discover UI and, where appropriate, network protocol behavior.
4. Implement the smallest provider-local transport.
5. Add deterministic fixtures/tests before relying on live behavior.
6. Validate chat E2.
7. Discover/validate model selection, streaming, reasoning/search/vision only if actually exposed.
8. Validate tool behavior; normalize only dialects actually observed.
9. Validate full tool round-trip if tools are claimed.
10. Record version, evidence level, limitations, latency/reliability samples, and lessons learned.

## Compatibility surface
Primary:
- `GET /v1/models`
- `POST /v1/chat/completions`

Planned after core provider baseline:
- `POST /v1/responses` shim, informed by AWA's practical Codex/Responses experience.

The API layer must translate shapes only; provider/browser/routing logic remains below it.

## Evidence policy
- E1: deterministic synthetic/unit/fixture evidence.
- E2: real provider web-session end-to-end evidence.
- E3: repeated runs across predefined independent windows with explicit success/latency/error thresholds.

No provider is labeled production-reliable or E3 based on a single successful live run.
