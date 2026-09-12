# KiloGate-WM Programming Model Status - 2026-09-12

## Scope

This is the closure report for the 2026-09-12 Web-model certification work in `hooshka-web-gateway`. It records which models are allowed for programming use in Kilo and closes all previously ambiguous rows as either certified or held with an explicit reason.

Evidence level remains **E2 smoke** unless a row explicitly says otherwise. This is not an E3/production reliability claim.

## Current Kilo programming allow-list

These models may be used for controlled programming work through Kilo because they have Kilo tool-execution evidence for the certified scope.

| Kilo model id | Certified scope | Status | Notes |
|---|---|---|---|
| `hooshka/deepseek-web` | Kilo read, grep/search, write, edit, bash/shell | `CERTIFIED_KILO_TOOL_EXECUTION_E2` | Dedicated DeepSeek Web profile/CDP route; not E3. |
| `hooshka/zai-web` | Alias to evidence-backed `zai:glm-5.2`; Kilo read, grep/search, write, edit, bash/shell | `CERTIFIED_KILO_TOOL_EXECUTION_E2` | Deep Think latency observed; still E2 only. |
| `hooshka/zai:glm-5.2` | Explicit GLM-5.2 baseline; Kilo read, grep/search, write, edit, bash/shell | `CERTIFIED_KILO_TOOL_EXECUTION_E2` | Same certification scope as `zai-web`. |
| `hooshka/qwen-web` | Alias to `qwen:qwen3.8-max` | `CERTIFIED_KILO_TOOL_EXECUTION_E2` | Certification does not transfer to other Qwen models. |
| `hooshka/qwen:qwen3.8-max` | Kilo read, grep/search, write, edit, bash/shell | `CERTIFIED_KILO_TOOL_EXECUTION_E2` | Qwen risk controls were observed in broader testing; this model is certified only for the recorded baseline. |
| `hooshka/chatgpt-web` | Existing Kilo E2 operational path | `AVAILABLE_E2_OPERATIONAL` | Not re-certified in the final Z.ai/Qwen closure pass; keep separate from the stricter newly closed rows. |

## Explicitly not enabled for programming

These models must not receive `tool_call=true` until the listed blockers are cleared and KiloGate-WM rows pass.

| Model id | Current evidence | Closure state | Kilo `tool_call` |
|---|---|---|---:|
| `hooshka/zai:glm-5.3` | Provider/Gateway API tool-call E2 passed; explicit Kilo row retried | `HOLD`, `failure_class=KILO_INIT_STALL_BEFORE_SESSION_PROMPT` | `false` |
| `hooshka/zai:x-preview-l` / GLM-5.3-Flash | Provider/Gateway API tool-call E2 passed | `HOLD`, dependent Kilo rows held after explicit Z.ai Kilo stall | `false` |
| `hooshka/qwen:qwen3.7-max` | Provider-direct base/tool protocol passed | `HOLD_QUOTA_LIMIT`; Gateway/Kilo blocked by daily usage limit | `false` |
| `hooshka/qwen:qwen3.7-plus` | Strong provider-direct evidence including stream states | `HOLD`; Gateway API and Kilo read/search/write/edit/bash still required | `false` |
| `hooshka/qwen:qwen3.6-plus` | Base matrix evidence only | `HOLD`; tool protocol/Gateway/Kilo not fully certified | `false` |
| `hooshka/qwen:qwen3.5-plus` | Base matrix evidence only | `HOLD`; tool protocol/Gateway/Kilo not fully certified | `false` |
| `hooshka/qwen:qwen3.5-omni-plus` | Unsupported/incompatible for required thinking/tool scope | `QUARANTINED/UNSUPPORTED` | `false` |

## Z.ai explicit-model closure

`zai:glm-5.3` and `zai:x-preview-l` / GLM-5.3-Flash were not left half-enabled. Temporary Kilo `tool_call=true` flags used during testing were reverted after the explicit Kilo row failed to reach a certifiable state.

Observed explicit Kilo retry for `zai:glm-5.3`:

```text
model: hooshka/zai:glm-5.3
marker: KGWM_KILO_zai:glm-5.3_TEXT_OK_20260912
kilo log: C:\Users\mahdi\.local\share\kilo\log\2026-09-12T094128.log
observed: Kilo bootstrap + kilocode-indexing
missing: service=session.prompt
missing: llm.provider=hooshka / modelID=zai:glm-5.3
missing: Kilo JSON type:"text" marker
classification: HOLD / KILO_INIT_STALL_BEFORE_SESSION_PROMPT
```

This is not a Z.ai model failure and not a Deep Think timeout. It is a Kilo CLI pre-dispatch/init stall for that explicit model row.

## Qwen closure

`qwen:qwen3.8-max` is the only Qwen model currently allowed for Kilo programming. The broader Qwen matrix remains model/state-specific. Manual screenshots and provider evidence corrected the earlier text-only classification, but certification is still scoped only to the tested model and state.

`qwen:qwen3.7-max` remains held because the provider showed a daily usage limit/wait-window. No bypass is allowed. Resume requires a read-only admission check after the wait window and then Gateway API plus Kilo tool rows.

## Current effective Kilo flags

```text
chatgpt-web          tool_call=true
deepseek-web         tool_call=true
zai-web              tool_call=true
zai:glm-5.2          tool_call=true
zai:glm-5.3          tool_call=false
zai:x-preview-l      tool_call=false
qwen-web             tool_call=true
qwen:qwen3.8-max     tool_call=true
qwen:qwen3.7-max     tool_call=false
qwen:qwen3.7-plus    tool_call=false
qwen:qwen3.6-plus    tool_call=false
qwen:qwen3.5-plus    tool_call=false
```

## Completion decision

All previously ambiguous items are now closed as one of:

- certified and enabled for the exact tested scope;
- held by quota/challenge/risk-control state;
- held by Kilo pre-dispatch/init stall;
- not enabled because Kilo full tool execution is missing.

No provider-family certification is claimed. No uncertified explicit model remains enabled for Kilo programming.
