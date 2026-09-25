# HWG 2.1.0 Production E3 Reliability - DeepSeek W2 Replacement

Date: 2026-09-25
Work Item: `HWG-WORK-013`
Release: `2.1.0`
Environment: Production `127.0.0.1:5000`
Scope: `deepseek-web / deepseek-web:default-account / deepseek-web`
Window: `W2` clean replacement
Decision: **PASS (3/3)**.

## Contract result

Window start: `2026-09-25T17:16:00.0466675Z`. W1 started at `2026-09-25T16:37:12.121044Z`, so the independent-window spacing is greater than 30 minutes. Exactly three probes were executed; no replay occurred.

| Run | Result | Expected / Observed | Commitment | Duration |
|---|---|---|---|---:|
| 1 | READY / AUTHENTICATED | `HWG_READY_F0B814B172EC` exact | terminal / retry=false | 14.590 s |
| 2 | READY / AUTHENTICATED | `HWG_READY_13FD3974BA2F` exact | terminal / retry=false | 16.534 s |
| 3 | READY / AUTHENTICATED | `HWG_READY_3BC0EC7919EA` exact | terminal / retry=false | 14.969 s |

No Provider/Account/Model substitution occurred. This replacement supersedes the procedurally invalid six-probe W2 attempt while preserving that record for audit history.

Raw runtime record: `.runtime-prod/e3-2.1.0-deepseek-w2-replacement-20260925.json`.

W2 = **PASS (3/3)**. Full E3 is not claimed until a valid W3 begins at least 30 minutes after this W2 and also passes 3/3.
