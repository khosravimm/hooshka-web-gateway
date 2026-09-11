# Hooshka Web Gateway — Provider Guide

## Capability matrix

| Provider | Model id | Transport | Stream provenance | Tools | Session note |
|---|---|---|---|---:|---|
| ChatGPT Web | `chatgpt-web` | CDP/Web provider path | buffered compatibility | yes | existing ChatGPT Web session/runtime |
| Qwen Web | `qwen-web`, `qwen:<upstream-id>` | browser backend controller | reconstructed | no | dynamic catalog; default `qwen3.8-max`; current guest quota is rate-limited |
| Z.ai Web | `zai-web`, `zai:<upstream-id>` | browser backend controller | reconstructed | no | dynamic catalog; default `glm-5.3`; default routing accepted E2 |
| DeepSeek Web | `deepseek-web` | manual Web Chat UI only; provider pending | not in Gateway | not executed | account healthy in UI; adapter pending |

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
- `/v1/models` exposes the current Qwen catalog with stable `qwen:` namespacing;
- `qwen-web` resolves through configurable `default_upstream_model`, currently `qwen3.8-max`;
- the active guest session reached its daily provider quota during 0.6.0 verification, so current completion attempts return normalized `rate_limit` instead of an empty successful response.

Search is intentionally not advertised until search provenance is independently verified. Tools are disabled.

## Z.ai Web

Z.ai research showed real backend completion/SSE behavior and provider-owned signature/session/challenge mechanisms.

The accepted strategy is not to generate or bypass anti-abuse proof. The browser/provider frontend owns that state while the adapter uses a backend-oriented controller/runtime path.

Observed 0.5.0 post-migration metadata:

- frontend `prod-fe-1.1.93`;
- authenticated session;
- upstream model observed as `x-preview-l`.

In 0.6.0, Z.ai catalog discovery exposes current upstream ids through the `zai:` namespace, while `zai-web` resolves to configurable `default_upstream_model` (currently `glm-5.3`). A controlled E2 request verified selector, observed backend request model, upstream metadata and exact response all aligned on GLM-5.3.

Only basic chat/reconstructed stream is accepted. Tools/search/vision/files remain disabled.

## DeepSeek Web

DeepSeek is no longer classified as blocked by the current Web Chat UI account state. A controlled manual Web Chat audit on 2026-09-12 observed an authenticated UI, no CAPTCHA/challenge/mute/suspension, a successful direct marker response, valid tool-envelope JSON generation, and tool-result continuation.

This does not make `deepseek-web` operational in the Gateway. The provider/adapter is still pending, and DeepSeek is not Kilo/full-agent certified until a complete Gateway/Kilo tool round trip passes.

See:

`DEEPSEEK_ACCOUNT_SUSPENSION_INCIDENT_2026-09-10.md`

`KILOGATE_WM_DEEPSEEK_WEBCHAT_AUDIT_2026-09-12.md`

## Adding capabilities

A capability moves to advertised state only after:

1. E0 protocol/source discovery;
2. E1 deterministic test coverage;
3. E2 real provider exercise;
4. capability metadata updated;
5. evidence document updated.

For tools, E2 must include a complete tool-call -> tool-result -> final-answer round trip, not merely detection of tool syntax.
