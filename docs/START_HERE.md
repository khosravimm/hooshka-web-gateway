# Hooshka Web Gateway Ã¢â‚¬â€ Start Here

**Current baseline:** 0.6.4
**Module id:** `web_gateway`
**Local path:** `D:\Code\hooshka-web-gateway`
**Windows service:** `HooshkaWebGateway`
**API:** `http://127.0.0.1:5000`

Hooshka Web Gateway is the single local gateway for governed access to supported Web-chat providers. Clients call one OpenAI-compatible API; provider-specific browser/session/backend behavior stays behind the gateway.

## What works now

| Provider | Canonical model | Basic chat | Stream API | Tools | Notes |
|---|---|---:|---:|---:|---|
| ChatGPT Web | `chatgpt-web` | E2 PASS | supported, buffered compatibility | E2 PASS | project-owned ChatGPT CDP runtime on 9224; Kilo large-prompt E2 PASS |
| Qwen Web | `qwen-web`, `qwen:qwen3.8-max` | blocked | supported, reconstructed | disabled | authenticated login pending; guest rejected |
| Z.ai Web | `zai-web`, `zai:glm-5.3` | E2 PASS | supported, reconstructed | disabled | Kilo text-only `summary` agent E2 PASS; tools disabled |
| DeepSeek Web | `deepseek-web` | blocked | blocked | blocked | current account-state circuit breaker |

E2 means a real Web-chat end-to-end test passed. It does not mean long-duration/E3 reliability.

## First five commands

From PowerShell:

```powershell
cd D:\Code\hooshka-web-gateway
.\service_manager.ps1 status
.\service_manager.ps1 config
Invoke-RestMethod http://127.0.0.1:5000/health
```

Authenticated endpoints require the runtime bearer key. Do not paste that key into documentation, tickets, chat transcripts, commits, screenshots, or shell history shared with others.

Run the deterministic test suite:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Expected 0.6.4 baseline: **63 passed**. Current Kilo E2 evidence: `chatgpt-web` PASS; `zai:glm-5.3` PASS with `summary` agent; Qwen not executed because the profile is still guest/401.

## Read next

- Operator: `OPERATIONS_RUNBOOK.md`
- Official login/session persistence: `../LOGIN_SESSION_GUIDE.md`
- Browser/runtime diagnostics: `BROWSER_OBSERVABILITY.md`
- API consumer: `API_REFERENCE.md`
- Practical examples: `PRACTICAL_USAGE.md`
- Hooshka integrator: `HOOSHKA_INTEGRATION_GUIDE.md`
- Developer: `DEVELOPMENT_GUIDE.md`
- Provider engineer: `PROVIDERS.md`
- Security reviewer: `SECURITY_GOVERNANCE.md`
- Configuration: `CONFIGURATION_REFERENCE.md`
- Troubleshooting: `TROUBLESHOOTING_CURRENT.md`
- Architecture: `ARCHITECTURE_CURRENT.md`
- Release handoff: `FINAL_REPORT_2026-09-10.md`
- Exact model evidence: `EXPLICIT_MODEL_SELECTION_EVIDENCE_2026-09-10.md`

## Core operating rules

1. Route explicitly by canonical model/provider; unknown routes fail closed.
2. Never silently fall back to another provider.
3. Do not replay a request after provider submission may have occurred.
4. Do not bypass CAPTCHA, WAF, account suspension, or provider risk controls.
5. Treat browser profiles, cookies, tokens and gateway API keys as secrets/security boundaries.
6. Do not advertise a capability until it has independent E2 evidence.
7. Keep the service on loopback unless a separately reviewed remote-access design is approved.
8. Do not send SUMS organizational/sensitive data through unofficial Web-chat providers without an explicit governance decision.
