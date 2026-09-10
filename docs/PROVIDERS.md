# Hooshka Web Gateway — Provider Guide

## Capability matrix

| Provider | Model id | Transport | Stream provenance | Tools | Session note |
|---|---|---|---|---:|---|
| ChatGPT Web | `chatgpt-web` | CDP/Web provider path | buffered compatibility | yes | existing ChatGPT Web session/runtime |
| Qwen Web | `qwen-web` | browser backend controller | reconstructed | no | dedicated Qwen profile; guest mode has worked |
| Z.ai Web | `zai-web` | browser backend controller | reconstructed | no | dedicated Z.ai profile; authenticated session observed |
| DeepSeek Web | `deepseek-web` | disabled while blocked | n/a | no | account-state circuit breaker |

## ChatGPT Web

The current adapter includes the mature tool-normalization path. Provider-specific tool dialects are normalized only when tool schemas are present and parsing is unambiguous.

Important rules:

- do not synthesize tool calls when the request declares no tools;
- required tool choice may use bounded repair, otherwise fail explicitly;
- detected but unparseable tool syntax is protocol ambiguity, not assistant prose;
- post-submit failures are not replayed.

## Qwen Web

Qwen integration prefers the provider's frontend controller/backend path over DOM chat automation.

Observed runtime characteristics include:

- frontend version discovery;
- chat creation and submit through provider frontend/controller behavior;
- answer reconstruction from provider runtime state;
- `thinking=false` mapped to the provider-supported Fast mode;
- `thinking=true` mapped to Auto;
- guest Web chat has passed E2.

Search is intentionally not advertised until search provenance is independently verified. Tools are disabled.

## Z.ai Web

Z.ai research showed real backend completion/SSE behavior and provider-owned signature/session/challenge mechanisms.

The accepted strategy is not to generate or bypass anti-abuse proof. The browser/provider frontend owns that state while the adapter uses a backend-oriented controller/runtime path.

Observed 0.5.0 post-migration metadata:

- frontend `prod-fe-1.1.93`;
- authenticated session;
- upstream model observed as `x-preview-l`.

Only basic chat/reconstructed stream is accepted. Tools/search/vision/files remain disabled.

## DeepSeek Web

DeepSeek is currently blocked by account state. The project retains research and incident knowledge but must not resume live automated testing until the account restriction is legitimately gone and a human review re-enables the provider.

See:

`DEEPSEEK_ACCOUNT_SUSPENSION_INCIDENT_2026-09-10.md`

## Adding capabilities

A capability moves to advertised state only after:

1. E0 protocol/source discovery;
2. E1 deterministic test coverage;
3. E2 real provider exercise;
4. capability metadata updated;
5. evidence document updated.

For tools, E2 must include a complete tool-call -> tool-result -> final-answer round trip, not merely detection of tool syntax.
