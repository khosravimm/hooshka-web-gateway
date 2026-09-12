# KiloGate-WM Web Chat Stop Contracts - 2026-09-12

## Basis

Runtime evidence:

```text
.runtime/kgwm_webchat_stop_surface_discovery_20260912.json
```

Mode:

```text
read_only_no_prompt_no_click
```

## Rule

Immediate provider-side Stop cannot be certified from timeout or stream-disconnect behavior alone. Each Web Chat needs a provider-specific contract based on:

```text
IDLE_SURFACE
ACTIVE_GENERATION_SURFACE
DOM_CONTROL_SURFACE
FRONTEND_RUNTIME_SURFACE
BACKEND_REQUEST_SURFACE
RISK_CONTROL_SURFACE
```

A row reaches `STOP_PROVIDER_CONFIRMED` only when the current prompt/session is matched, generation starts, the provider-side stop path is executed, active state clears, and the final marker does not later appear.

## Discovered idle surfaces

| Provider | Idle composer/send surface | Runtime/backend observation | Stop contract status |
|---|---|---|---|
| `qwen-web` | `textarea.message-input-textarea`, placeholder `Ask Qwen` | `window.__mwbQwenController` present; session state `idle`; `stopResponse` / `stopAllResponses` known | strongest candidate; active row required |
| `zai-web` | `textarea#chat-input`; `div[aria-label="Send Message"]`; `button#send-message-button` | `__mwbZaiHistoryStore`, `__mwbZaiConfigStore`, `__mwbZaiModule` present on runtime tab; backend resources include auth/config/models and chat completion endpoints | active DOM/backend discovery required |
| `deepseek-web` | textarea placeholder `Message DeepSeek` | DeepSeek frontend and `/api/v0/...` resources observed; no idle stop candidate | prior stop attempt failed; active stop surface required |
| `chatgpt-web` | `div#prompt-textarea[contenteditable=true]`, aria-label `Chat with ChatGPT` | ChatGPT app resources observed; backend stream surface not mapped by idle row | active surface required |

## Findings

Idle state exposes no visible Stop button for any provider. Therefore active-generation discovery is mandatory before another certification attempt.

Qwen has the best structural signal because the runtime controller exposes stop functions. Z.ai and DeepSeek need active DOM/backend discovery because no reliable idle stop function was found. ChatGPT also needs active DOM discovery.

## Next runner requirement

The next executable tool must run one provider at a time:

```text
1. send one long safe request;
2. observe DOM/runtime/backend every 500ms while active;
3. record button morphs, session state and request lifecycle;
4. attempt provider halt only after active surface is mapped;
5. classify as confirmed only if no final marker continues after halt.
```

## Active discovery update

See:

```text
docs/KILOGATE_WM_ACTIVE_STOP_DISCOVERY_2026-09-12.md
```

Current active-discovery findings:

```text
qwen-web / qwen:qwen3.8-max: STOP_PROVIDER_CONFIRMED_CANDIDATE for runtime stop path
DeepSeek: ACTIVE_SURFACE_CAPTURED but no Stop control found
Z.ai: ACTIVE_DISCOVERY_RUNNER_NAVIGATION_LOST
ChatGPT: no new active row in this pass
```


## Contract update - 2026-09-12T14:30Z

### Qwen

The Qwen runtime contract remains the strongest known stop path: `controller.stopResponse`, `pool.stopAllResponses`, and `session.stopResponse` are discoverable and callable. The repeat confirmation row was blocked by a quota/high-demand wait-window, so the contract stays at candidate level and is not promoted to final certification.

### DeepSeek

DeepSeek exposed unlabeled SVG candidates during active generation, including floating controls, left-composer controls, and right-composer controls. These candidates are not safe enough for production cancellation. The production hook must not click unlabeled SVG-only controls unless a future contract proves a specific DOM path or backend cancellation path. Current DeepSeek immediate-stop status is failed/uncertified.

### Z.ai

Z.ai active DOM/backend discovery is now rebind-aware and no longer fails only because of navigation/context replacement. Active stop-like SVGs exist, but no confirmed stop control or provider runtime stop function has been proven. Z.ai remains inconclusive for immediate stop.


## ChatGPT contract update - 2026-09-12T14:56Z

ChatGPT Stop Contract now requires an authenticated execution surface. The observed configured CDP page was logged out and therefore invalid for certification.

Allowed production Stop selectors:

- `button[data-testid="stop-button"]`
- visible button or role-button controls with explicit Stop / Stop generating / Stop streaming / cancel-response / interrupt semantics

Disallowed as certification proof:

- logged-out landing page composer
- Send button text accidentally matching generic patterns
- Escape-only interruption
- generic icon-only heuristics without a signed contract

Certification remains blocked by `CHATGPT_AUTH_REQUIRED_FOR_STOP_CERT` until the CDP 9224 ChatGPT session is authenticated.

## ChatGPT Stop Contract — confirmed row

`chatgpt-web` now has a confirmed Stop contract for the current ChatGPT Web UI surface:

```text
provider: chatgpt-web
required authenticated surface: accounts-profile-button present and login/sign-up absent
required composer surface: visible #prompt-textarea / ProseMirror composer
send control: button[data-testid="send-button"] / #composer-submit-button
active stop control: button[data-testid="stop-button"]
active stop aria: Stop answering
post-stop evidence: stop button disappears and assistant final marker does not appear
status: STOP_PROVIDER_CONFIRMED
```

The adapter must bind to the authenticated tab with a valid composer instead of using the first `chatgpt.com` tab. The Gateway must not treat Escape as proof of Stop; Escape remains only a fallback attempt.
