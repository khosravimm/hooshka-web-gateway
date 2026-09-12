# KiloGate-WM Active Stop Surface Discovery - 2026-09-12

## Scope

This report records active-generation stop-surface discovery performed after the provider-specific Stop Contract requirement was introduced.

Evidence files:

```text
.runtime/kgwm_qwen_active_stop_surface_20260912.json
.runtime/kgwm_deepseek_active_stop_surface_20260912.json
.runtime/zai_active_stop_surface.py execution trace: navigation context lost before evidence flush
```

## Qwen Web / qwen:qwen3.8-max

Result:

```text
STOP_PROVIDER_CONFIRMED_CANDIDATE
```

Evidence summary:

```text
active_seen: true
session state before: idle
session state during row: sending
runtime stop functions present: controller.stopResponse, pool.stopAllResponses, session.stopResponse
stop call result: controller.stopResponse + pool.stopAllResponses + session.stopResponse called
post-stop state: destroyed, then empty/no active session
final marker after 16s: false
service readiness after row: ready
```

Interpretation:

```text
Qwen now has a valid provider-runtime stop path for the tested state.
This confirms the provider-side runtime path, not yet the physical Kilo Stop button UI path.
```

Certification boundary:

```text
Confirmed candidate for: qwen-web / qwen:qwen3.8-max / browser_controller / thinking=true / search=false / runtime stop path
Not yet generalized to: all Qwen models, all thinking/search states, or Kilo UI Stop button click.
```

## DeepSeek Web

Result:

```text
ACTIVE_SURFACE_CAPTURED
```

Evidence summary:

```text
active_seen: true
stop_like_count: 0
final marker after observation: false
stream transport: opened and observed
service readiness after row: ready
```

Interpretation:

```text
DeepSeek active generation was observed, but no reliable Stop control was discovered in the captured DOM surface.
This supports the previous conclusion that DOM/ESC cancellation is insufficient for DeepSeek immediate-stop certification.
```

Certification boundary:

```text
not certified
```

## Z.ai Web / glm-5.2

Result:

```text
ACTIVE_DISCOVERY_RUNNER_NAVIGATION_LOST
```

Evidence summary:

```text
runner sent row but Playwright evaluate lost execution context due page navigation/context replacement
no valid active-surface evidence was flushed
post-run UI was idle/landing-like and service readiness remained ready
```

Interpretation:

```text
This is a runner robustness issue, not a model/tool failure. Z.ai needs a resilient active-discovery runner that tracks page replacement and rebinds to the active runtime tab.
```

Certification boundary:

```text
not certified
```

## ChatGPT Web

No new active-discovery row was executed in this pass. Existing status remains:

```text
STOP_NOT_CERTIFIED_NO_ACTIVE_START_EVIDENCE
```

## Required next engineering work

```text
1. Promote the Qwen runtime stop path from candidate to certified only after one repeat row reproduces the result.
2. Build resilient active-discovery runners that survive page navigation/replacement.
3. For DeepSeek, discover a real active Stop selector or backend cancellation path; DOM/ESC is not enough.
4. For Z.ai, re-run after rebinding logic is added.
5. For ChatGPT, run active discovery only after navigation stability is verified.
```
