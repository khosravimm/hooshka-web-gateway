# HWG dev.6 Control Plane E2 — 2026-09-22

Scope: Development runtime only (`127.0.0.1:5080`). Production/legacy port 5000 was not started or modified.

## Cutover

- Pre-cutover checkout: `53b6705`, dev.4-era runtime with local modifications.
- Local state preserved in Git stash `pre-dev6-cutover-20260922-0150` and external backup `D:\Code\_backup\hwg-pre-dev6-cutover-20260922-0150`.
- Checkout fast-forwarded to `feb23f4` on `develop`.
- Old 5080 listener was stopped and the gateway restarted from the updated checkout.
- Live `/panel/api/meta`: version `1.0.0-dev.6`, commit `feb23f4`, branch `develop`.
## Live control-plane evidence

- `/panel/api/browser-runtimes` reported exactly two Browser Runtime groups:
  - CDP 9330 + `shared-profile` with ChatGPT, Z.ai and DeepSeek as Provider/Tab children.
  - CDP 9325 + `qwen-profile` with Qwen as the single child.
- Both CDPs reported ready.
- `/panel/api/runtime/orchestration` reported Desktop Runtime Agent reachable on 5181 and its Scheduled Task installed.
- Served Provider provisioning UI contains runtime selection and relationship preview surfaces.
- Raw Provider-form inputs for CDP URL and Profile Directory are absent.
- Panel JavaScript consumes `/browser-runtimes` and submits `runtime_key` rather than raw CDP/Profile values.

This evidence proves live deployment and serving of the dev.6 Control Plane contract. It does not close account-isolation design, human UX acceptance, or E3 reliability.
