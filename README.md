# Hooshka Web Gateway

**Canonical id:** `hooshka-web-gateway`
**Hooshka module:** `web_gateway`
**Current release:** `0.5.1`

Hooshka Web Gateway is the unified local API gateway for governed access to supported Web-chat providers. It gives Hooshka, local agents and compatible clients one OpenAI-style interface while isolating provider-specific browser, session, frontend and transport behavior.

## Current provider baseline

| Provider | Canonical model | Status | Current accepted scope |
|---|---|---|---|
| ChatGPT Web | `chatgpt-web` | E2 operational | chat, stream compatibility, tool-call path |
| Qwen Web | `qwen-web` | E2 operational | chat, reconstructed stream, reasoning mode |
| Z.ai Web | `zai-web` | E2 operational | basic chat, reconstructed stream |
| DeepSeek Web | `deepseek-web` | blocked | current account state prevents live E2 |

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
ChatGPT    Qwen     Z.ai
 Web       Web      Web
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

Start with:

```text
docs/START_HERE.md
```

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

Accepted 0.5.0 deterministic baseline: **54 passed**.

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
