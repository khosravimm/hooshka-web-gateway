# HWG 2.1.0 Production E3 Reliability — DeepSeek W3 Replacement Deferred

Date: 2026-09-25
Target scope: `deepseek-web / deepseek-web:default-account / deepseek-web`
Target endpoint: Production `127.0.0.1:5000`

## Result
**DEFERRED — zero provider probes executed.** The anti-replay batch was not started because the Production identity precondition failed.

## Preconditions observed
- Replacement check time: `2026-09-25T19:25:51Z`, more than 30 minutes after failed W3-clean start `2026-09-25T18:38:50.974072Z`.
- 5000 LISTEN, PID `13308`.
- 5080 LISTEN.
- 9330 LISTEN, PID `9760`.
- 5181 LISTEN; watchdog enabled, no current errors.
- DeepSeek account session: `AUTHENTICATED`.
- **Blocking mismatch:** `GET /panel/api/meta` on port 5000 reported version `2.1.1-dev.full-audit-remediation.20260925-1907`, branch `develop`, commit `06d25a2`, rather than immutable release `2.1.0` / release commit `9f50e11...` recorded by the Production release evidence.
- Process inspection showed port 5000 PID `13308` executing `D:\Code\hooshka-web-gateway\main.py` from the mutable develop working tree.

## Governance decision
Starting W3 under this identity would mix a Dev checkout with the release-specific E3 series and invalidate the claim. Therefore no POST was sent to `/panel/api/providers/deepseek-web/readiness/probe`; no W3 replacement raw probe artifact was created; W1 and accepted W2 replacement remain valid historical evidence, while E3 remains **NOT CLAIMED**.

## Required remediation before another W3 replacement
Production 5000 must be restored to an immutable/separate `2.1.0` deployment identity without changing the shared login profile or disturbing 5080/9330. Only after `/panel/api/meta` independently proves release `2.1.0` should a new, single three-probe anti-replay W3 replacement be attempted.
