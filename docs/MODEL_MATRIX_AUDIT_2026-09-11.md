# Hooshka Web Gateway Model Matrix Audit — 2026-09-11

Release target: `0.6.7`
Evidence level: `E2` for successful real Web-chat end-to-end checks; no E3 reliability claim is made.

## Executive result

- Current Gateway catalog: 8 model ids.
- Current Kilo Hooshka catalog: 8 model ids.
- Catalog consistency: PASS (`missing_in_kilo=[]`).
- Current certified models: 8/8 PASS for Direct Gateway and Kilo Code completion.
- Required-tool fail-closed: PASS for all current Qwen text-only models; ChatGPT is tracked separately as tool-capable.
- Z.ai is not advertised in 0.6.7 because the latest current retest returned `Z.ai first-event timeout`; historical Z.ai rows are retained below as `NOT_ADVERTISED`, not certified.

## Current certified catalog

| # | Model ID | Provider | Gateway Catalog | Kilo Catalog | Authenticated | Direct Gateway | Kilo Code | Required Tool Policy | Requested Upstream Model | Backend Request Model | Selected UI Model | Final Verdict | Failure Reason | Evidence Level |
|---:|---|---|---:|---:|---|---|---|---|---|---|---|---|---|---|
| 1 | `qwen-web` | `qwen-web` | yes | yes | authenticated | PASS | PASS | PASS | - | qwen3.8-max | - | PASS | - | E2 |
| 2 | `qwen:qwen3.7-plus` | `qwen-web` | yes | yes | authenticated | PASS | PASS | PASS | - | qwen3.7-plus | - | PASS | - | E2 |
| 3 | `qwen:qwen3.8-max` | `qwen-web` | yes | yes | authenticated | PASS | PASS | PASS | - | qwen3.8-max | - | PASS | - | E2 |
| 4 | `qwen:qwen3.7-max` | `qwen-web` | yes | yes | authenticated | PASS | PASS | PASS | - | qwen3.7-max | - | PASS | - | E2 |
| 5 | `qwen:qwen3.6-plus` | `qwen-web` | yes | yes | authenticated | PASS | PASS | PASS | - | qwen3.6-plus | - | PASS | - | E2 |
| 6 | `qwen:qwen3.5-plus` | `qwen-web` | yes | yes | authenticated | PASS | PASS | PASS | - | qwen3.5-plus | - | PASS | - | E2 |
| 7 | `qwen:qwen3.5-omni-plus` | `qwen-web` | yes | yes | authenticated | PASS | PASS | PASS | - | qwen3.5-omni-plus | - | PASS | - | E2 |
| 8 | `chatgpt-web` | `chatgpt-web` | yes | yes | completion-auth-gate-passed | PASS | PASS | SKIP | - | - | - | PASS | - | E2 |

## Not advertised / retained for traceability

These rows were present in earlier exploratory/dynamic catalog observations or historical evidence, but are not part of the 0.6.7 current catalog. They must not be treated as available Kilo/Gateway models until a fresh E2 matrix passes.

| # | Model ID | Provider | Gateway Catalog | Kilo Catalog | Last Direct Status | Last Kilo Status | Final Verdict | Reason |
|---:|---|---|---:|---:|---|---|---|---|
| 1 | `zai-web` | `zai-web` | no | no | FAIL | PASS | NOT_ADVERTISED | Z.ai first-event timeout |
| 2 | `zai:glm-5.3` | `zai-web` | no | no | FAIL | PENDING | NOT_ADVERTISED | Z.ai first-event timeout |
| 3 | `zai:glm-5.2` | `zai-web` | no | no | FAIL | PENDING | NOT_ADVERTISED | Requested Z.ai model is not available in the current session |
| 4 | `zai:x-preview-l` | `zai-web` | no | no | PENDING | PENDING | NOT_ADVERTISED | Not advertised in 0.6.7; current Z.ai UI/controller E2 evidence is not stable enough for certification. |
| 5 | `zai:GLM-5-Turbo` | `zai-web` | no | no | PENDING | PENDING | NOT_ADVERTISED | Not advertised in 0.6.7; current Z.ai UI/controller E2 evidence is not stable enough for certification. |
| 6 | `zai:GLM-5v-Turbo` | `zai-web` | no | no | PENDING | PENDING | NOT_ADVERTISED | Not advertised in 0.6.7; current Z.ai UI/controller E2 evidence is not stable enough for certification. |
| 7 | `zai:glm-4.7` | `zai-web` | no | no | PENDING | PENDING | NOT_ADVERTISED | Not advertised in 0.6.7; current Z.ai UI/controller E2 evidence is not stable enough for certification. |
| 8 | `zai:glm-4.6v` | `zai-web` | no | no | PENDING | PENDING | NOT_ADVERTISED | Not advertised in 0.6.7; current Z.ai UI/controller E2 evidence is not stable enough for certification. |
| 9 | `zai:0727-106B-API` | `zai-web` | no | no | PENDING | PENDING | NOT_ADVERTISED | Not advertised in 0.6.7; current Z.ai UI/controller E2 evidence is not stable enough for certification. |
| 10 | `zai:0727-360B-API` | `zai-web` | no | no | PENDING | PENDING | NOT_ADVERTISED | Not advertised in 0.6.7; current Z.ai UI/controller E2 evidence is not stable enough for certification. |
| 11 | `zai:GLM-4.1V-Thinking-FlashX` | `zai-web` | no | no | PENDING | PENDING | NOT_ADVERTISED | Not advertised in 0.6.7; current Z.ai UI/controller E2 evidence is not stable enough for certification. |
| 12 | `zai:deep-research` | `zai-web` | no | no | PENDING | PENDING | NOT_ADVERTISED | Not advertised in 0.6.7; current Z.ai UI/controller E2 evidence is not stable enough for certification. |
| 13 | `zai:zero` | `zai-web` | no | no | PENDING | PENDING | NOT_ADVERTISED | Not advertised in 0.6.7; current Z.ai UI/controller E2 evidence is not stable enough for certification. |
| 14 | `zai:glm-4-flash` | `zai-web` | no | no | PENDING | PENDING | NOT_ADVERTISED | Not advertised in 0.6.7; current Z.ai UI/controller E2 evidence is not stable enough for certification. |
| 15 | `zai:0808-360B-DR` | `zai-web` | no | no | PENDING | PENDING | NOT_ADVERTISED | Not advertised in 0.6.7; current Z.ai UI/controller E2 evidence is not stable enough for certification. |
| 16 | `zai:glm-4-air-250414` | `zai-web` | no | no | PENDING | PENDING | NOT_ADVERTISED | Not advertised in 0.6.7; current Z.ai UI/controller E2 evidence is not stable enough for certification. |

## Gate notes

- `/ready` is bounded and no longer allowed to hang indefinitely on provider probing.
- `/v1/models` is bounded and preserves static/base aliases only on provider discovery timeout.
- Qwen `thinking` mode is now changed only when requested explicitly; omitted `thinking` preserves the provider/model default and fixed the prior `thinking_mode_failed` path for `qwen3.7-max` and `qwen3.5-omni-plus`.
- ChatGPT DOM composer fill failure falls back to the authenticated backend-intercept path that was already validated for large Kilo prompts.
- No passwords, cookies, bearer tokens, authorization headers, CAPTCHA proofs, or raw auth bodies are recorded in this report.

