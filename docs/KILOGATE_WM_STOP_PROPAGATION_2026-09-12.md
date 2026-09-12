# KiloGate-WM Stop Propagation Report - 2026-09-12

## Question

Determine whether pressing Stop in Kilo / closing a streaming client immediately stops provider-side Web Chat generation.

## Result

Stop propagation is now implemented as a Gateway/provider best-effort path, but immediate provider-side cancellation is **not yet certified** for all Web Chat providers.

## Implementation

The Gateway streaming path now emits SSE keepalive frames while waiting for provider chunks. If the streaming generator exits before `[DONE]`, it calls:

```text
provider.cancel_active_generation("stream_client_disconnected")
```

before cancelling the local future.

Provider hooks added:

| Provider | Hook method | Current certification |
|---|---|---|
| Qwen | frontend `stopResponse` / `stopAllResponses` best-effort | implemented; live test skipped by risk admission |
| Z.ai | DOM stop/cancel/interrupt search + Escape fallback | hook reached; no stop candidate clicked |
| DeepSeek | DOM stop/cancel/interrupt search + Escape fallback | hook reached; no stop candidate clicked |
| ChatGPT | known stop button selectors + Escape fallback | implemented; not live-tested in this pass |

## Evidence

Runtime evidence files:

```text
.runtime/kgwm_stop_propagation_deepseek_20260912.json
.runtime/kgwm_stop_propagation_zaiweb_20260912.json
.runtime/kgwm_stop_propagation_qwen38_20260912.json
```

Log evidence after stream client disconnect:

```text
Provider active-generation cancel hook result for deepseek-web:
  supported=True, cancelled=False, method=dom_stop_button, clicked=False, candidates=0

Provider active-generation cancel hook result for zai-web:
  supported=True, cancelled=False, method=dom_stop_button, clicked=False, candidates=0
Stopping Z.ai Web Chat after failed/cancelled stream
```

Qwen was not live-tested because the admission check detected risk text before sending the row. No further Qwen live-call was made.

## Interpretation

- Before this change, Kilo/client Stop could leave provider-side Web Chat work running.
- After this change, Gateway observes stream disconnects and invokes a provider cancel hook.
- For DeepSeek and Z.ai, the hook reached the provider transport, but the live run did not prove an immediate provider-side Stop button click.
- Therefore the correct current classification is `STOP_HOOK_REACHED` / `STOP_PROVIDER_ATTEMPTED`, not `STOP_PROVIDER_CONFIRMED`.

## Next certification requirement

To certify immediate Stop, each provider/model surface must pass a live row proving:

```text
1. long generation starts;
2. Kilo/client Stop occurs;
3. provider-side active-generation state is observed;
4. provider-side stop/cancel control or controller hook is executed;
5. active-generation state disappears;
6. the same marker does not continue after cancellation.
```

Until then, Stop behavior must be described as **best-effort and observable**, not guaranteed immediate cancellation.

## Immediate Stop certification execution - 2026-09-12T13:10Z

A stricter live certification pass was executed with a direct provider instance over the same CDP surfaces. This was not a UI click on the Kilo button itself; it exercised the equivalent Gateway/provider cancellation path that Kilo Stop is expected to trigger: active provider generation starts, `cancel_active_generation("immediate_stop_certification")` is invoked, and the page is observed for continuation of the same marker.

Runtime evidence file:

```text
.runtime/kgwm_immediate_stop_certification_20260912.json
```

Result summary:

| Provider row | Result | Certification decision |
|---|---|---|
| `deepseek-web` | Cancel hook reached; DOM stop candidate was not found; Escape was sent; the final marker later appeared in the provider page. | `STOP_PROVIDER_FAILED_CONTINUED_AFTER_ATTEMPT` |
| `zai-web` / `glm-5.2` | The row did not produce valid active-start evidence for the exact prompt before cancellation. | `STOP_NOT_CERTIFIED_NO_ACTIVE_START_EVIDENCE` |
| `qwen-web` / `qwen:qwen3.8-max` | The row was skipped before prompt submission because the admission check detected risk text in the Qwen page. | `SKIPPED_RISK_VISIBLE_BEFORE_TEST` |
| `chatgpt-web` | The row did not produce valid active-start evidence; the run also observed a navigation-level `ERR_CONNECTION_CLOSED` warning for `chatgpt.com`. | `STOP_NOT_CERTIFIED_NO_ACTIVE_START_EVIDENCE` |

Key finding:

```text
No provider reached STOP_PROVIDER_CONFIRMED in this pass.
DeepSeek produced negative evidence: the response continued to the final marker after the stop attempt.
```

Operational implication:

Kilo/Gateway Stop must still be treated as observable best-effort cancellation, not as guaranteed immediate provider-side cancellation. For DeepSeek specifically, the current Stop mechanism is insufficient for provider-side immediate stop.


## Active Stop closure update - 2026-09-12T14:30Z

Evidence files:

- `.runtime/kgwm_qwen_final_stop_cert_20260912.json`
- `.runtime/kgwm_deepseek_active_dom_backend_discovery_20260912.json`
- `.runtime/kgwm_deepseek_final_stop_cert_20260912.json`
- `.runtime/kgwm_zai_active_dom_backend_discovery_20260912.json`
- `.runtime/kgwm_zai_final_stop_cert_20260912.json`

| Provider/model | Evidence result | Classification |
|---|---|---|
| `qwen-web` / `qwen:qwen3.8-max` | Repeat final row hit provider quota/high-demand wait-window before a clean confirmation row could complete. The marker later seen in the DOM belonged to the submitted prompt, not confirmed assistant continuation. | `HOLD_QUOTA_LIMIT` |
| `deepseek-web` | Active generation was observed. A right-composer SVG candidate was clicked by the hook, but the provider response continued and the final marker later appeared in the page. Generic SVG candidates were then disabled for the production hook. | `STOP_PROVIDER_FAILED_CONTINUED_AFTER_ATTEMPT` |
| `zai-web` | Rebind-aware active DOM/backend discovery captured an active row. Final stop row opened and was disconnected, but the hook still did not identify a confirmed stop control; no second marker was observed. | `STOP_PROVIDER_ATTEMPTED_INCONCLUSIVE` |

No provider is promoted to `STOP_PROVIDER_CONFIRMED` by this update. Immediate Web Chat stop remains a provider-specific capability requiring a signed Stop Contract and repeat confirmation.
