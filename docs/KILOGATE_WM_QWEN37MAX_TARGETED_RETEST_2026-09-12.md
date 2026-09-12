# KiloGate-WM Qwen3.7-Max targeted retest - 2026-09-12

## Scope

Target model: `qwen:qwen3.7-max` / upstream `qwen3.7-max`.

This retest was requested after the earlier Qwen full matrix showed mixed `FAIL/HOLD` rows for `qwen3.7-max`. The targeted rerun used reduced batches and explicit monitoring for CAPTCHA/challenge and quota/usage-limit states.

## Admission

Before retest:

```text
CDP 9225 connected: yes
authenticated: yes
captcha/challenge visible: no
high-demand/quota visible: no
active generation: no
zombie qwen process: no
```

## Provider-direct base matrix

```json
{
  "summary": {
    "PASS": 13
  },
  "rows": 13
}
```

Result:

```text
thinking: default,false,true
search: false,true
stream: non-stream,stream
all rows: PASS
```

## Provider-direct tool protocol matrix

```json
{
  "summary": {
    "PASS": 24
  },
  "rows": 24
}
```

Result:

```text
required tool_call: PASS across all thinking/search/stream states
tool_result continuation: PASS across all thinking/search/stream states
```

## Gateway API matrix interruption

Gateway API matrix was started after provider-direct base+tool passed. During the run, Qwen displayed a provider usage-limit banner:

```text
You have reached the daily usage limit. Please wait 18 hours before trying again.
```

This is not classified as model failure. It is a provider risk-control state.

Risk closure:

```json
{
  "summary": {
    "PASS": 3,
    "FAIL": 21,
    "HOLD": 12
  },
  "expected_rows": 36,
  "executed_or_recorded_rows": 36,
  "risk_hold_rows_added": 12
}
```

Gateway API passed rows before quota interruption:

```text
3 PASS
```

Gateway API rows blocked or invalidated by quota interruption:

```text
21 FAIL recorded by runner before user screenshot clarified daily usage limit
12 HOLD due quota_limit_observed
```

The FAIL rows should not be used as proof that `qwen3.7-max` lacks capability; they occurred under a provider daily-limit state and require rerun after the wait window.

## Quota monitor requirement

KiloGate-WM was updated to version `0.5.1` to make quota monitoring explicit. All future live runners must stop and inform the user when they detect:

```text
daily usage limit
usage limit
quota
high demand
too many requests
rate limit
please wait N hours
```

No bypass is allowed: no account rotation, no IP/session/profile workaround, and no scripted challenge handling.

## Certification impact

Current status:

```text
qwen:qwen3.7-max provider-direct base: PASS
qwen:qwen3.7-max provider-direct tool protocol: PASS
qwen:qwen3.7-max Gateway API: HOLD_QUOTA_LIMIT / needs rerun after wait window
qwen:qwen3.7-max Kilo full tool execution: NOT RUN / blocked by quota
```

Therefore `qwen:qwen3.7-max` must remain `tool_call=false` in Kilo until Gateway API and Kilo read/search/write/edit/bash pass after quota cooldown.

## Resume rule

Resume only after the wait window expires and a read-only admission check passes:

```text
1. no quota/daily-limit/high-demand banner
2. no CAPTCHA/challenge modal
3. authenticated session
4. no active generation
5. no zombie test process
6. rerun only remaining Gateway API rows first
7. then run Kilo text/read/grep/write/edit/bash in a reduced batch
```
