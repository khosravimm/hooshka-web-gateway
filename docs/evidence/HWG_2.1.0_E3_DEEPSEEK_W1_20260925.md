# HWG 2.1.0 Production E3 Reliability — DeepSeek W1

Date: 2026-09-25
Work Item: `HWG-WORK-013`
Release: `2.1.0`
Environment: Production `127.0.0.1:5000`
Scope: `deepseek-web / deepseek-web:default-account / deepseek-web`
Window: `W1`
Decision: **PASS (3/3)** — not yet full E3.

This is a fresh release-specific E3 series. The older 2026-09-22 Dev W1 remains historical evidence and is not reused to claim reliability for Production 2.1.0.

| Run | Result | Access | Expected / Observed | Duration | Commitment |
|---|---|---|---|---:|---|
| 1 | PASS | AUTHENTICATED | `HWG_READY_39F24F5F3FE6` exact | 14.523 s | terminal / retry=false |
| 2 | PASS | AUTHENTICATED | `HWG_READY_986CAC8697CB` exact | 12.285 s | terminal / retry=false |
| 3 | PASS | AUTHENTICATED | `HWG_READY_7C621DFEE0C7` exact | 12.000 s | terminal / retry=false |

W1 started at `2026-09-25T16:37:12.121044Z`.

W2 and W3 must start at least 30 minutes apart and use the exact same Provider/Account/Model/Production scope. No E3 claim is allowed until both remaining windows pass 3/3.

Raw runtime record:
`.runtime-prod/e3-2.1.0-deepseek-w1-20260925.json`
