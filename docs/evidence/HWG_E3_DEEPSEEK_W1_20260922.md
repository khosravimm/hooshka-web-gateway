# HWG E3 Reliability — DeepSeek W1 Evidence

Date: 2026-09-22
Work Item: `HWG-WORK-013`
Scope: `deepseek-web / deepseek-web:default-account / deepseek-web`
Window: `W1`
Level: repeated E2 window; **not yet full E3**

## Predefined window result
Three automated-validation readiness probes were executed against the live development gateway on port 5080.

| Run | Result | Duration | Commitment |
|---|---|---:|---|
| 1 | READY, exact token | 32.87 s | terminal / retry=false |
| 2 | READY, exact token | 17.98 s | terminal / retry=false |
| 3 | READY, exact token | 17.94 s | terminal / retry=false |

All three expected tokens exactly matched observed tokens. No replay was allowed after commitment.

## Decision
W1 = **PASS (3/3)**.

This does not authorize an E3 reliability claim. W2 and W3 must use the same Provider/Account/Model scope and begin at least 30 minutes apart according to `HWG_E3_RELIABILITY_PROGRAM_V1.md`.
