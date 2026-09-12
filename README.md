# Hooshka Web Gateway

**Canonical id:** `hooshka-web-gateway`
**Hooshka module:** `web_gateway`
**Current release:** `0.6.6`

Hooshka Web Gateway is the unified local API gateway for governed access to supported Web-chat providers. It gives Hooshka, local agents and compatible clients one OpenAI-style interface while isolating provider-specific browser, session, frontend and transport behavior.

## Current provider baseline

| Provider | Canonical model | Status | Current accepted scope |
|---|---|---|---|
| ChatGPT Web | `chatgpt-web` | E2 operational via Kilo | chat, stream compatibility, tool-call path, large agent prompt transport |
| Qwen Web | `qwen-web`, `qwen:qwen3.8-max` | KiloGate-WM E2 tool-capable smoke PASS for `qwen3.8-max`; other explicit models remain separately uncertified | model-aware thinking/search, reconstructed stream; read/grep/write/edit/bash passed for `qwen3.8-max`; `qwen3.5-omni-plus` quarantined |
| Z.ai Web | `zai-web`, `zai:glm-5.2` | KiloGate-WM E2 tool-capable smoke PASS for `zai-web` / `glm-5.2`; explicit `glm-5.3` and `GLM-5.3-Flash` remain held | Web Chat/CDP 9223; read/grep/write/edit/bash passed for `glm-5.2`; `glm-5.3`/`x-preview-l` provider/API E2 passed but Kilo explicit rows are HOLD and `tool_call=false` |
| DeepSeek Web | `deepseek-web` | KiloGate-WM E2 tool-capable smoke PASS | browser-UI transport via dedicated 9226 runtime; read/grep/write/edit/bash passed; not E3/production-certified |

This release is an **E2 baseline**, not an E3/production-reliability claim.

## Architecture

```text
Hooshka / local client
        |
        v
OpenAI-compatible localhost API
        |
        v
Exact fail-closed router
   |        |        |
ChatGPT    Qwen     Z.ai     DeepSeek
 Web       Web      Web      Web
```

Provider-specific fallback stays within a provider. There is no silent cross-provider fallback.

## Start

```powershell
cd D:\Code\hooshka-web-gateway
.\service_manager.ps1 status
.\service_manager.ps1 start
```

Service:

```text
HooshkaWebGateway
```

API bind:

```text
http://127.0.0.1:5000
```

## Main API endpoints

- `GET /health`
- `GET /ready`
- `GET /health/deep`
- `GET /modes`
- `GET /v1/models`
- `POST /v1/chat/completions`
- `POST /v1/chat/code`
- `POST /v1/chat/conversation`

Authenticated operational calls require the runtime bearer key.

## Documentation

**Primary discovery document for humans and agents:**

```text
HOOSHKA_WEB_GATEWAY_START_HERE.md
```

The detailed documentation index is in `docs/README.md`.

Then use:

- `docs/ARCHITECTURE_CURRENT.md`
- `docs/API_REFERENCE.md`
- `docs/CONFIGURATION_REFERENCE.md`
- `docs/OPERATIONS_RUNBOOK.md`
- `docs/PROVIDERS.md`
- `docs/SECURITY_GOVERNANCE.md`
- `docs/HOOSHKA_INTEGRATION_GUIDE.md`
- `docs/DEVELOPMENT_GUIDE.md`
- `docs/TROUBLESHOOTING_CURRENT.md`
- `docs/FINAL_REPORT_2026-09-10.md`

Historical research/evidence documents remain under `docs/`.

## Development gate

```powershell
.\.venv\Scripts\python.exe -m compileall -q .
.\.venv\Scripts\python.exe -m pytest -q
git diff --check
```

Accepted deterministic baseline before DeepSeek integration: **70 passed**. DeepSeek, Z.ai and Qwen now have KiloGate-WM E2 smoke evidence for read/search/write/edit/shell tool paths on their certified baselines. Qwen certification is limited to `qwen3.8-max`; other explicit Qwen models require separate tool-execution evidence.

## Security rules

- Loopback only by default.
- Runtime secrets outside Git.
- Browser profiles are security boundaries.
- No CAPTCHA/WAF/account-suspension bypass.
- No silent provider substitution.
- No post-commit automatic replay.
- No stress/load testing against personal Web-chat accounts.
- Do not send organizational/sensitive SUMS data through unofficial Web-chat transports without an explicit governance decision.

## Repository

Canonical GitHub repository:

```text
khosravimm/hooshka-web-gateway
```

Legacy project name `mcp-web-bridge` is retained only in historical/migration compatibility records.

Z.ai KiloGate-WM E2 smoke passed read/search/write/edit/shell through the browser Web Chat path using the evidence-backed `glm-5.2` baseline. A later selector retest showed `zai:glm-5.3` and `zai:x-preview-l` / `GLM-5.3-Flash` pass provider-level and Gateway API E2 tool-call checks, but they are not yet Kilo full tool-execution certified. Deep Think latency remains a separate E3 reliability concern.


Qwen KiloGate-WM retest corrected the previous text-only status: `qwen:qwen3.8-max` passed provider-level, Gateway API and Kilo read/search/write/edit/bash tool checks. Manual Web Chat screenshots also motivated XML-ish `tool_call` parser hardening. This remains E2 smoke certification, not E3 reliability.


KiloGate-WM programming model status is recorded in `docs/KILOGATE_WM_PROGRAMMING_MODEL_STATUS_2026-09-12.md`. Explicit Z.ai `glm-5.3` / `x-preview-l` rows are held as `KILO_INIT_STALL_BEFORE_SESSION_PROMPT`; Qwen `qwen3.7-max` remains held by provider quota. These models are intentionally left `tool_call=false`.


Stop/cancel propagation is best-effort and documented in `docs/KILOGATE_WM_STOP_PROPAGATION_2026-09-12.md`; immediate provider-side Stop is not certified unless a provider/model row proves it.

Immediate Stop certification on 2026-09-12 found no provider with confirmed immediate provider-side cancellation; DeepSeek continued to the final marker after the stop attempt.
