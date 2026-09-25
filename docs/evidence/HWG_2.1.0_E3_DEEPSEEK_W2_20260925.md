# HWG 2.1.0 Production E3 Reliability - DeepSeek W2

Date: 2026-09-25
Work Item: `HWG-WORK-013`
Release: `2.1.0`
Environment: Production `127.0.0.1:5000`
Scope: `deepseek-web / deepseek-web:default-account / deepseek-web`
Window: `W2`
Decision: **INVALID WINDOW - clean replacement required; no E3 claim.**

## What happened

The first bounded automated-validation batch started at `2026-09-25T17:11:36.864649Z`, more than 30 minutes after W1. Its three probes all passed the functional contract. The orchestration call then timed out outside the gateway after the batch had executed. The same bounded runner was replayed once, producing a second three-probe batch beginning at `2026-09-25T17:12:37.872587Z`.

Therefore six probes were executed in the intended W2 window. This violates the strict instruction that a window run **exactly three** probes. Functional behavior was 6/6 PASS, but W2 is not accepted as an E3 window.

## Functional observations

| Batch | Run | Result | Expected / Observed | Commitment |
|---|---:|---|---|---|
| 1 | 1 | READY / AUTHENTICATED | `HWG_READY_62AED112F892` exact | terminal / retry=false |
| 1 | 2 | READY / AUTHENTICATED | `HWG_READY_7C9A6559551B` exact | terminal / retry=false |
| 1 | 3 | READY / AUTHENTICATED | `HWG_READY_49BDA5A96195` exact | terminal / retry=false |
| 2 | 1 | READY / AUTHENTICATED | `HWG_READY_D5DB87C81251` exact | terminal / retry=false |
| 2 | 2 | READY / AUTHENTICATED | `HWG_READY_B69BFA6350BC` exact | terminal / retry=false |
| 2 | 3 | READY / AUTHENTICATED | `HWG_READY_2B57ADDAC686` exact | terminal / retry=false |

No Provider/Account/Model substitution occurred. Production remained on port 5000 and CDP remained on 9330. No product code was changed by this W2 run.

## Decision

W2 is **procedurally invalid** despite 6/6 functional success. A future clean replacement W2 must execute exactly three probes, and W3 cannot complete the full E3 claim until a valid W2 exists and the >=30-minute independent-window spacing contract is satisfied.

Raw runtime record:
`.runtime-prod/e3-2.1.0-deepseek-w2-20260925.json`

## Supersession

Superseded by clean replacement W2 starting `2026-09-25T17:16:00.0466675Z`, recorded in `docs/evidence/HWG_2.1.0_E3_DEEPSEEK_W2_REPLACEMENT_20260925.md`. This invalid six-probe window remains preserved for audit history and is not counted toward E3.
