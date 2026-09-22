# HWG Failure / Retry / Commitment E2 Evidence — 2026-09-22

## Scope

Work item: `HWG-WORK-012 — Failure retry commitment conformance`.

This evidence verifies that Web Chat provider submission now exposes a standard commitment state and forbids replay after submission may have started.

## Implemented contract

- `not_sent`: retry may be allowed.
- `maybe_sent`: replay is forbidden unless reconciliation explicitly proves safety.
- `committed`: provider-side submission has been initiated/accepted.
- `terminal`: the request reached a terminal observed state.

Provider metadata and provider errors now expose:

```json
{"commitment_state":"...","retry_allowed":false}
```

## Deterministic tests

Targeted tests passed:

- `tests/test_consolidated_093.py`
- `tests/test_retry_boundary.py`
- `tests/test_work012_commitment_contract.py`
- Provider/readiness regression set

Key assertions:

- retry is only safe in `not_sent`.
- errors after `maybe_sent` include `retry_allowed=false`.
- ChatGPT, DeepSeek, Qwen and Z.ai expose commitment metadata in the provider path.
- Functional Readiness evidence captures commitment metadata from provider response.

## Live E2

A governed DeepSeek readiness probe was executed via:

`POST /panel/api/providers/deepseek-web/readiness/probe`

with `execution_authority=automated_validation`.

Observed E2 result:

```json
{
  "state": "READY",
  "ready": true,
  "expected": "HWG_READY_40891A164EB9",
  "observed": "HWG_READY_40891A164EB9",
  "commitment": {
    "commitment_state": "terminal",
    "retry_allowed": false
  }
}
```

## Result

Scoped E2 PASS for the DeepSeek functional-readiness path.

`HWG-WORK-012` can be closed for the implemented commitment/retry contract, while broader E3 reliability remains under provider certification work.
