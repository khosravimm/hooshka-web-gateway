# KiloGate-WM Qwen Full Matrix - 2026-09-12

## Purpose

This document records the stricter Qwen retest after the KiloGate-WM v0.5.0 correction. The correction requires model-by-model, state-by-state coverage across thinking, search, stream and tool modes. A pass for one Qwen model or state must not be transferred to another.

## KiloGate-WM process update

`docs/KILOGATE_WM_CONTROL_PIPELINE.md` was updated to version `0.5.0` with:

```text
Mandatory Cartesian coverage rule
model × thinking × search × stream × tool_mode materialization
provider alias scoping rule
CAPTCHA / human-verification challenge controls
```

## Risk-control interruption

During the live Qwen matrix, the user reported two CAPTCHA/human-verification events and manually solved them. No screenshot was captured. This is recorded as:

```text
evidence_class: self_reported_no_screenshot
user_intervention: manual_challenge_solve_reported
policy_result: pause live matrix; no automated challenge solve/bypass; remaining live rows become HOLD
```

A read-only CDP check after cleanup found the Qwen session reachable and no visible CAPTCHA-like text at that moment, but that does not erase the risk-control observation.

## Evidence files

```text
.runtime/kilogate_qwen_full_base_matrix_20260912.json
.runtime/kilogate_qwen_full_tool_protocol_matrix_20260912.json
.runtime/kilogate_qwen_full_tool_protocol_matrix_risk_closed_20260912.json
```

Runtime scripts under `.runtime/` are operational evidence generators and are not product code.

## Base matrix result

Scope:

```text
provider_direct
5 advertised Qwen Chat models
thinking: default, false, true
search: false, true
stream: non_stream, stream
```

Summary:

```json
{
  "rows": 61,
  "summary": {
    "PASS": 50,
    "FAIL": 6,
    "HOLD": 5
  },
  "by_model": {
    "qwen:qwen3.8-max": {
      "FAIL": 3,
      "HOLD": 2,
      "PASS": 7
    },
    "qwen:qwen3.7-plus": {
      "PASS": 12
    },
    "qwen:qwen3.7-max": {
      "PASS": 6,
      "FAIL": 3,
      "HOLD": 3
    },
    "qwen:qwen3.6-plus": {
      "PASS": 12
    },
    "qwen:qwen3.5-plus": {
      "PASS": 12
    }
  }
}
```

Base matrix failures/holds:

- `qwen:qwen3.8-max` thinking=`default` search=`False` stream=`False` -> `FAIL` / upstream_error
- `qwen:qwen3.8-max` thinking=`default` search=`False` stream=`True` -> `HOLD` / base non-stream row did not pass; stream row stopped by KiloGate-WM v0.5.0
- `qwen:qwen3.8-max` thinking=`default` search=`True` stream=`False` -> `FAIL` / upstream_error
- `qwen:qwen3.8-max` thinking=`default` search=`True` stream=`True` -> `HOLD` / base non-stream row did not pass; stream row stopped by KiloGate-WM v0.5.0
- `qwen:qwen3.8-max` thinking=`true` search=`False` stream=`True` -> `FAIL` / upstream_error
- `qwen:qwen3.7-max` thinking=`default` search=`True` stream=`False` -> `FAIL` / upstream_error
- `qwen:qwen3.7-max` thinking=`default` search=`True` stream=`True` -> `HOLD` / base non-stream row did not pass; stream row stopped by KiloGate-WM v0.5.0
- `qwen:qwen3.7-max` thinking=`false` search=`True` stream=`False` -> `FAIL` / upstream_error
- `qwen:qwen3.7-max` thinking=`false` search=`True` stream=`True` -> `HOLD` / base non-stream row did not pass; stream row stopped by KiloGate-WM v0.5.0
- `qwen:qwen3.7-max` thinking=`true` search=`False` stream=`False` -> `FAIL` / upstream_error
- `qwen:qwen3.7-max` thinking=`true` search=`False` stream=`True` -> `HOLD` / base non-stream row did not pass; stream row stopped by KiloGate-WM v0.5.0

Interpretation:

```text
qwen:qwen3.7-plus: base matrix fully PASS
qwen:qwen3.6-plus: base matrix fully PASS
qwen:qwen3.5-plus: base matrix fully PASS
qwen:qwen3.8-max: base matrix has FAIL/HOLD in default and one stream state
qwen:qwen3.7-max: base matrix has FAIL/HOLD in selected search/thinking states
```

## Tool protocol matrix result

The tool protocol matrix was executed only for base-PASS rows, as required by the v0.5.0 stop rules.

Raw executed summary before pause:

```json
{
  "rows": 46,
  "summary": {
    "PASS": 44,
    "FAIL": 1,
    "HOLD": 1
  },
  "by_model": {
    "qwen:qwen3.8-max": {
      "PASS": 14
    },
    "qwen:qwen3.7-plus": {
      "PASS": 24
    },
    "qwen:qwen3.7-max": {
      "PASS": 6,
      "FAIL": 1,
      "HOLD": 1
    }
  }
}
```

Risk-closed summary after materializing unexecuted rows as HOLD:

```json
{
  "expected_rows": 98,
  "executed_or_recorded_rows": 98,
  "risk_hold_rows_added": 52,
  "summary": {
    "PASS": 44,
    "FAIL": 1,
    "HOLD": 53
  },
  "by_model": {
    "qwen:qwen3.8-max": {
      "PASS": 14
    },
    "qwen:qwen3.7-plus": {
      "PASS": 24
    },
    "qwen:qwen3.7-max": {
      "PASS": 6,
      "FAIL": 1,
      "HOLD": 5
    },
    "qwen:qwen3.6-plus": {
      "HOLD": 24
    },
    "qwen:qwen3.5-plus": {
      "HOLD": 24
    }
  }
}
```

Important observations:

```text
qwen:qwen3.7-plus completed all 24 provider-direct tool protocol rows: PASS
qwen:qwen3.8-max completed 14 provider-direct tool protocol rows for its base-PASS states: PASS
qwen:qwen3.7-max had partial execution before pause: 4 PASS, 1 FAIL, 1 HOLD
qwen:qwen3.6-plus and qwen:qwen3.5-plus base rows are promising but provider-direct tool protocol rows were held due risk-control pause
```

## Certification impact

This run does not authorize family-wide Qwen tool certification.

Current certification statements:

```text
qwen:qwen3.8-max retains the earlier KiloGate-WM E2 tool-capable smoke certification, but the new v0.5 matrix shows state-specific gaps that must be documented.
qwen:qwen3.7-plus has strong provider-direct base+tool evidence, including stream states, but still needs Gateway API and real Kilo tool execution before tool_call=true.
qwen:qwen3.6-plus has full base PASS but tool protocol/Kilo rows are HOLD due risk-control pause.
qwen:qwen3.5-plus has full base PASS but tool protocol/Kilo rows are HOLD due risk-control pause.
qwen:qwen3.7-max is not certifiable yet because base and tool rows contain FAIL/HOLD.
qwen3.5-omni-plus remains outside this matrix and quarantined for Kilo.
```

Kilo configuration must remain conservative:

```text
Only qwen-web as alias to the already certified baseline and qwen:qwen3.8-max may keep tool_call=true.
No other explicit Qwen model may be promoted to Kilo tool_call=true until Gateway API + Kilo read/search/write/edit/bash pass for that exact model/state scope.
```

## Resume rule

The next live run must use reduced batches after cooldown:

```text
1. read-only admission check: CDP alive, authenticated, no challenge, no active generation, no zombie process
2. finish qwen:qwen3.7-plus Gateway API stream/non-stream + tool_result rows
3. run qwen:qwen3.7-plus Kilo read/search/write/edit/bash
4. only then consider enabling tool_call=true for qwen:qwen3.7-plus
5. continue one model at a time; do not rerun a large Cartesian matrix immediately
```
