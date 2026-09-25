# HWG 2.1.0 Production E3 Reliability — DeepSeek W3 Replacement

Date: 2026-09-25
Work Item: `HWG-WORK-013`
Release: `2.1.0`
Environment: Production `127.0.0.1:5000`
Exact scope: `deepseek-web / deepseek-web:default-account / deepseek-web`
Window: `W3 replacement`
Decision: **PASS (3/3)**.

## Replacement preconditions

- Failed `W3-clean` started at `2026-09-25T18:38:50.974072Z` and failed at probe 1 with runtime absent; its artifact and lock were preserved and not replayed or overwritten.
- Replacement preflight at approximately `2026-09-25T19:55Z` was more than 76 minutes after the failed W3 start.
- Safe-Laptop was reachable and stable.
- Production `5000`, Dev `5080`, Desktop Runtime Agent `5181`, and CDP `9330` were all listening before the replacement batch.
- Production identity was corrected without modifying tag `v2.1.0` or Production source: `HooshkaWebGateway` now runs from detached worktree `D:\Code\hooshka-web-gateway-prod-2.1.0` at tag SHA `74929915533634956a5db41ba9210d213220e986`.
- Production `/panel/api/meta` reported `version=2.1.0`, `commit=7492991`; Dev `5080` remained on `2.1.1-dev.full-audit-remediation.20260925-1907` / `develop`.
- Shared Chrome/CDP `9330` and the existing shared login profile were preserved through the Production service restart.
- Independent session verification before the batch returned `AUTHENTICATED`, account `deepseek-web:default-account`, composer ready, and provider `deepseek-web`.

## Anti-replay batch

Exactly one replacement batch was started. It contained exactly three POST requests to:

`/panel/api/providers/deepseek-web/readiness/probe`

with `execution_authority=automated_validation`. The retained lock prevents replay. No retry was required.

| Run | Result | Provider / Account / Model | Expected / Observed | Commitment |
|---|---|---|---|---|
| 1 | READY / AUTHENTICATED | `deepseek-web` / `deepseek-web:default-account` / `deepseek-web` | `HWG_READY_BD0FF78BA83E` exact | terminal / retry=false |
| 2 | READY / AUTHENTICATED | `deepseek-web` / `deepseek-web:default-account` / `deepseek-web` | `HWG_READY_7120A492BF08` exact | terminal / retry=false |
| 3 | READY / AUTHENTICATED | `deepseek-web` / `deepseek-web:default-account` / `deepseek-web` | `HWG_READY_7914E86E58A6` exact | terminal / retry=false |

Raw runtime record:
`.runtime-prod/e3-2.1.0-deepseek-w3-replacement-20260925.json`

Anti-replay lock:
`.runtime-prod/e3-2.1.0-deepseek-w3-replacement-20260925.lock`

## E3 decision

The release-specific series now satisfies the predefined repeated-window contract for the exact scope only:

- W1: PASS 3/3 — `2026-09-25T16:37:12.121044Z`
- Accepted W2 replacement: PASS 3/3 — `2026-09-25T17:16:00.0466675Z`
- W3 replacement: PASS 3/3 — after the failed W3-clean was preserved and a new eligible window was opened more than 30 minutes later.

Therefore **E3 is claimed only for `deepseek-web / deepseek-web:default-account / deepseek-web` on Production release 2.1.0 under this tested Safe-Laptop configuration**. This does not establish E3 for ChatGPT, Z.ai, Qwen, discovered providers, other accounts/models, or a broader HWG provider fleet.

## Related evidence

- `docs/evidence/HWG_2.1.0_E3_DEEPSEEK_W1_20260925.md`
- `docs/evidence/HWG_2.1.0_E3_DEEPSEEK_W2_REPLACEMENT_20260925.md`
- `docs/evidence/HWG_2.1.0_E3_DEEPSEEK_W3_REPLACEMENT_DEFERRED_20260925.md`
- `docs/evidence/HWG_DESKTOP_RUNTIME_AGENT_RESILIENCE_E2_20260925.md`
