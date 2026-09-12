# Hooshka Web Gateway — Provider Guide

## Capability matrix

| Provider | Model id | Transport | Stream provenance | Tools | Session note |
|---|---|---|---|---:|---|
| ChatGPT Web | `chatgpt-web` | CDP/Web provider path | buffered compatibility | yes | existing ChatGPT Web session/runtime |
| Qwen Web | `qwen-web`, `qwen:qwen3.8-max` | browser backend controller | reconstructed | yes, E2 smoke for `qwen3.8-max` | default `qwen3.8-max`; Kilo read/grep/write/edit/bash passed for the certified baseline |
| Z.ai Web | `zai-web`, `zai:<upstream-id>` | browser Web Chat/CDP controller | reconstructed | yes, E2 smoke for `glm-5.2` | `zai-web` resolves to evidence-backed `glm-5.2`; Kilo read/grep/write/edit/bash passed; Deep Think timing remains E3 work |
| DeepSeek Web | `deepseek-web` | browser UI via dedicated CDP runtime | buffered compatibility | yes, E2 smoke | dedicated `.runtime/deepseek-profile` on 9226; Kilo read/grep/write/edit/bash passed |

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

- authenticated Qwen Web Chat runtime on CDP 9225 is available;
- `/v1/models` exposes the current Qwen catalog with stable `qwen:` namespacing;
- `qwen-web` resolves through configurable `default_upstream_model`, currently `qwen3.8-max`;
- `qwen:qwen3.8-max` passed KiloGate-WM E2 tool-capable smoke retest;
- Gateway tools are enabled only for the certified upstream model list, currently `qwen3.8-max`;
- other explicit Qwen models remain tool-uncertified until separately tested;
- `qwen3.5-omni-plus` remains quarantined for Kilo.


## Z.ai Web

Z.ai research showed real backend completion/SSE behavior and provider-owned signature/session/challenge mechanisms.

The accepted strategy is not to generate or bypass anti-abuse proof. The browser/provider frontend owns that state while the adapter uses a backend-oriented controller/runtime path.

Observed 0.5.0 post-migration metadata:

- frontend `prod-fe-1.1.93`;
- authenticated session;
- upstream model observed as `x-preview-l`.

In the Z.ai KiloGate-WM audit, catalog discovery exposed upstream ids through the `zai:` namespace, while `zai-web` was moved to the evidence-backed `glm-5.2` baseline because that model had reproducible Web Chat/runtime evidence. KiloGate-WM E2 smoke certification passed read, grep/search, write, edit and bash/shell through the browser Web Chat path.

This is an E2 tool-capable smoke result, not E3/production reliability. Search/vision/files remain disabled unless independently certified. Deep Think final-continuation latency is tracked separately.

## DeepSeek Web

DeepSeek is no longer classified as blocked by the current Web Chat UI account state. A controlled manual Web Chat audit on 2026-09-12 observed an authenticated UI, no CAPTCHA/challenge/mute/suspension, a successful direct marker response, valid tool-envelope JSON generation, and tool-result continuation.

`deepseek-web` is now implemented as a Gateway provider using the project-owned DeepSeek browser profile on CDP port 9226. KiloGate-WM E2 smoke certification passed read, grep, write, edit and bash tool paths through Kilo. This is still an E2 smoke result, not an E3/production-reliability claim.

See:

`DEEPSEEK_ACCOUNT_SUSPENSION_INCIDENT_2026-09-10.md`

`KILOGATE_WM_DEEPSEEK_WEBCHAT_AUDIT_2026-09-12.md`

`KILOGATE_WM_DEEPSEEK_GATEWAY_KILO_AUDIT_2026-09-12.md`

## Adding capabilities

A capability moves to advertised state only after:

1. E0 protocol/source discovery;
2. E1 deterministic test coverage;
3. E2 real provider exercise;
4. capability metadata updated;
5. evidence document updated.

For tools, E2 must include a complete tool-call -> tool-result -> final-answer round trip, not merely detection of tool syntax.

### Z.ai KiloGate-WM status

`zai-web` is KiloGate-WM E2 tool-capable smoke certified on the evidence-backed `glm-5.2` Web Chat baseline. Kilo executed read, grep/search, write, edit and bash/shell. Deep Think timing and final-continuation latency remain E3 reliability work.

A later selector-focused retest upgraded `zai:glm-5.3` and `zai:x-preview-l` / `GLM-5.3-Flash` to provider/Gateway API E2 tool-call PASS after fixing model-option selection and Flash label normalization. That retest does not automatically enable Kilo `tool_call=true` for those explicit models; they still need separate Kilo read/search/write/edit/bash evidence.

### Qwen KiloGate-WM status

`qwen:qwen3.8-max` is KiloGate-WM E2 tool-capable smoke certified after the 2026-09-12 retest. Provider-level and Gateway API tool-call round-trips passed, and Kilo executed read, grep/search, write, edit and bash/shell. The retest also added XML-ish `tool_call` parser hardening for Web Chat outputs observed manually.

This certification is limited to `qwen3.8-max`; it does not certify other explicit Qwen models, `qwen3.5-omni-plus`, `coder.qwen.ai`, or E3/production reliability.

See `docs/KILOGATE_WM_QWEN_GATEWAY_KILO_RETEST_2026-09-12.md`.
