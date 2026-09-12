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
