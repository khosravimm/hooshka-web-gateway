# Web Chat Thinking/Search E2 Matrix — 2026-09-16

Release line: 0.7.1  
Scope: authenticated Web Chat providers exposed by Hooshka Web Gateway.  
Base URL: `http://127.0.0.1:5000`  
Probe prompt: `Return exactly: HWG_FEATURE_PROBE`

## Acceptance criterion

A matrix row is accepted only when all of the following are true:

1. The request is submitted through the Hooshka Web Gateway API.
2. The provider returns a real completion.
3. The effective Thinking/Search state is visible in provider metadata, observed payload fields, or verified UI state.
4. The observed state matches the requested state.

The literal response text is recorded as operational context only. For feature-control acceptance, `provider_meta.features` or provider-specific backend feature evidence is authoritative.

## Runtime readiness

Before the final matrix pass:

- `/health`: `ok`
- `/ready`: `ready`
- Provider CDP listeners:
  - ChatGPT: `127.0.0.1:9224`
  - Qwen: `127.0.0.1:9225`
  - Z.ai: `127.0.0.1:9223`
  - DeepSeek: `127.0.0.1:9226`

## Results

| Provider | Model used | Thinking | Search | Result | Evidence |
|---|---|---:|---:|---|---|
| Qwen Web | `qwen-web` -> `qwen3.8-max` | false | false | PASS | `provider_meta.features={thinking:false, search:false}` |
| Qwen Web | `qwen-web` -> `qwen3.8-max` | true | false | PASS | `provider_meta.features={thinking:true, search:false}` |
| Qwen Web | `qwen-web` -> `qwen3.8-max` | false | true | PASS | `provider_meta.features={thinking:false, search:true}` |
| Qwen Web | `qwen-web` -> `qwen3.8-max` | true | true | PASS | `provider_meta.features={thinking:true, search:true}` |
| ChatGPT Web | `chatgpt-web` | false | false | PASS | `provider_meta.features={thinking:false, search:false, thinking_effort_index:0}` |
| ChatGPT Web | `chatgpt-web` | true | false | PASS | `provider_meta.features={thinking:true, search:false, thinking_effort_index:1}` |
| ChatGPT Web | `chatgpt-web` | false | true | PASS | `provider_meta.features={thinking:false, search:true, thinking_effort_index:0}` |
| ChatGPT Web | `chatgpt-web` | true | true | PASS | `provider_meta.features={thinking:true, search:true, thinking_effort_index:1}` |
| DeepSeek Web | `deepseek-web` | false | false | PASS | `provider_meta.features={thinking:false, search:false}` |
| DeepSeek Web | `deepseek-web` | true | false | PASS | `provider_meta.features={thinking:true, search:false}` |
| DeepSeek Web | `deepseek-web` | false | true | PASS | `provider_meta.features={thinking:false, search:true}` |
| DeepSeek Web | `deepseek-web` | true | true | PASS | `provider_meta.features={thinking:true, search:true}` |
| Z.ai Web | `zai:glm-5.3` | false | false | PASS | `backend_features={enable_thinking:false, reasoning_effort:low, web_search:false, auto_web_search:false}` |
| Z.ai Web | `zai:glm-5.3` | true | false | PASS | `backend_features={enable_thinking:true, reasoning_effort:max, web_search:false, auto_web_search:false}` |
| Z.ai Web | `zai:glm-5.3` | false | true | PASS | `backend_features={enable_thinking:false, reasoning_effort:low, web_search:true, auto_web_search:true}` |
| Z.ai Web | `zai:glm-5.3` | true | true | PASS | `backend_features={enable_thinking:true, reasoning_effort:max, web_search:true, auto_web_search:true}` |

## Findings fixed during this pass

### ChatGPT composer effort control drift

The current ChatGPT Web composer can render the reasoning-effort pill as a visible, enabled React/Radix control while Playwright's default click action never satisfies the stability heuristic. The gateway now resolves the reasoning-effort control near the active composer and uses a bounded fallback click path only after verifying the control is present, visible and enabled. The resulting state is still verified after interaction; unknown or mismatched state remains fail-closed.

### DeepSeek toggle selector drift

Current DeepSeek Web renders DeepThink/Search toggles as `.ds-toggle-button` elements without consistent native button or role semantics. The gateway now includes this current selector and re-resolves the toggle after React node replacement before verifying the observed state.

## Limitations

- ChatGPT `thinking=false` means minimum available reasoning effort, not proof of zero upstream hidden reasoning.
- Z.ai evidence is based on authenticated frontend completion payload rewrite and observed backend feature fields. This validates feature control, not search-result quality.
- No E3 reliability claim is made. This is a single authenticated E2 pass for the listed runtime/session state.
