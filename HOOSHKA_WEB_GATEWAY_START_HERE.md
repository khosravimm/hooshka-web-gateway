# Hooshka Web Gateway — Start Here

> **Canonical discovery document for humans and agents**
>
> If you are opening this repository for the first time, read this file before changing code, configuration, browser runtimes, services, or provider integrations.

## Project identity

- **Product:** Hooshka Web Gateway
- **Technical id:** `hooshka-web-gateway`
- **Hooshka module id:** `web_gateway`
- **Current baseline:** `1.0.0-dev.5`
- **Current local checkout:** `D:\Code\hooshka-web-gateway`
- **Canonical project/repository id:** `hooshka-web-gateway`
- **Windows service:** `HooshkaWebGateway`
- **Local API:** `http://127.0.0.1:5000`
- **Canonical GitHub repository:** `khosravimm/hooshka-web-gateway`

Legacy names such as `mcp-web-bridge` and `WebLLMBridge` are historical/compatibility identifiers only.

## Mission

Hooshka Web Gateway is the single governed gateway for connecting Hooshka and local clients to supported Web-chat providers through one OpenAI-compatible local API.

Provider-specific browser, session, frontend, backend, signature, CAPTCHA/challenge, transport, retry and parsing behavior must remain behind this module boundary.

Hooshka itself should consume the gateway API and must not depend directly on provider internals.

## Current operational status

| Provider | Canonical model | Basic chat | Stream API | Tools | Evidence/status |
|---|---|---:|---:|---:|---|
| ChatGPT Web | `chatgpt-web` | PASS | buffered compatibility | PASS | E2 operational through Kilo; provider-side Stop certified for the Gateway/Kilo stream-disconnect path |
| Qwen Web | `qwen-web`, `qwen:qwen3.8-max` | PASS | reconstructed | PASS on certified baseline | KiloGate-WM E2 tool-capable smoke PASS for `qwen3.8-max`; other explicit models require separate certification |
| Z.ai Web | `zai-web`, `zai:glm-5.2` | PASS | reconstructed | PASS on certified baseline | KiloGate-WM E2 tool-capable smoke PASS for `glm-5.2`; explicit `glm-5.3` / `x-preview-l` remain Kilo HOLD |
| DeepSeek Web | `deepseek-web` | PASS | buffered compatibility | PASS on certified baseline | KiloGate-WM E2 tool-capable smoke PASS; not E3/production-certified |

**Evidence levels**

- E0 — source/research evidence
- E1 — deterministic unit/synthetic/prototype evidence
- E2 — real Web-chat end-to-end evidence
- E3 — repeated predefined reliability evidence across independent windows

The current release is an **E2 operational baseline**, not an E3 reliability claim.

## Agent discovery rules

Any agent working in this repository should follow this order:

1. Read this file.
2. Read `docs/README.md` for the canonical documentation map.
3. Read `docs/ARCHITECTURE_CURRENT.md` before changing architecture or routing.
4. Read `docs/PROVIDERS.md` before changing a provider.
5. Read `docs/SECURITY_GOVERNANCE.md` before touching sessions, credentials, browser profiles, authentication, rate controls, or provider anti-abuse behavior.
6. Read `docs/OPERATIONS_RUNBOOK.md` before changing the Windows service or browser runtime lifecycle.
7. Read `docs/DEVELOPMENT_GUIDE.md` before implementing or releasing changes.
8. Use historical/evidence documents only to understand prior findings; when they conflict with canonical current docs, verify against current code/config and follow the canonical current docs.

Do not infer capabilities from provider marketing, frontend labels, old evidence, or another provider's behavior. Capability claims must follow local evidence.

## Canonical sources of truth

HWG uses separate authority layers so that current implementation cannot silently override the production mission.

**Normative product and control authority (what HWG must become and which gates apply):**

1. `docs/governance/HWG_NEXT_GENERATION_PRODUCTION_MISSION_V1.md` (`HWG-MISSION-NG-001`) — mandatory upper-level production mission and acceptance gates.
2. The parent architecture referenced by that mission (`HWG-ARCH-001`) when present in the repository; material deviations require ADR + synchronized mission/architecture/tests/docs.
3. `docs/governance/WEBCHAT_PROVIDER_INTEGRATION_KNOWLEDGE_TRANSFER_V1.md` (`HWG-KT-WEBCHAT-001`) — canonical provider/runtime engineering playbook and reusable operational invariants.
4. Approved ADRs and versioned schemas/contracts.

**Current implementation truth (what is actually implemented now):**

1. executable code and deterministic tests;
2. `config.yaml` and versioned runtime/profile configuration;
3. this root Start Here document and `docs/README.md`;
4. canonical current documents listed below.

**Evidence truth:** scoped E0/E1/E2/E3 records remain authoritative only for their recorded version/session/account/provider scope. Newer scoped evidence may supersede older evidence, but it does not waive a normative Mission requirement. A conflict between current code/config and the Mission is a tracked gap until resolved or formally changed through ADR/versioned governance.

Canonical current documents:

- `docs/governance/HWG_NEXT_GENERATION_PRODUCTION_MISSION_V1.md`
- `docs/governance/WEBCHAT_PROVIDER_INTEGRATION_KNOWLEDGE_TRANSFER_V1.md`
- `docs/governance/HWG_NG_REQUIREMENTS_TRACEABILITY.md`


- `docs/ARCHITECTURE_CURRENT.md`
- `LOGIN_SESSION_GUIDE.md`
- `docs/BROWSER_OBSERVABILITY.md`
- `docs/API_REFERENCE.md`
- `docs/PRACTICAL_USAGE.md`
- `docs/CONFIGURATION_REFERENCE.md`
- `docs/OPERATIONS_RUNBOOK.md`
- `docs/PROVIDERS.md`
- `docs/SECURITY_GOVERNANCE.md`
- `docs/HOOSHKA_INTEGRATION_GUIDE.md`
- `docs/DEVELOPMENT_GUIDE.md`
- `docs/TROUBLESHOOTING_CURRENT.md`
- `docs/FINAL_REPORT_2026-09-10.md`
- `docs/EXPLICIT_MODEL_SELECTION_EVIDENCE_2026-09-10.md`

## Architecture at a glance

```text
Hooshka / local agent / compatible client
                  |
                  v
       Hooshka Web Gateway
       127.0.0.1:5000
                  |
         request normalization
                  |
                  v
       exact fail-closed router
          /        |        \
         /         |         \
 chatgpt-web    qwen-web     zai-web
      |             |            |
 provider-local transport / browser runtime
                  |
                  v
          normalized response
```

There is **no silent cross-provider fallback**.

## Transport policy

For each provider, prefer:

1. direct backend HTTP/SSE/WebSocket when safe and reproducible;
2. browser-context fetch or official frontend controller;
3. network/controller capture;
4. DOM interaction only as a last provider-local fallback.

Backend-first never means bypassing provider controls.

## Core safety and engineering invariants

1. **Exact routing:** unknown or ambiguous model/provider ids fail closed.
2. **No cross-provider substitution:** a failed provider request is not silently sent elsewhere.
3. **Commitment-aware retry:** retry only when it is provable that upstream submission did not occur.
4. **No replay after possible submit:** ambiguous post-submit failure is terminal for that attempt.
5. **No CAPTCHA/WAF/suspension bypass:** use provider-normal flows; ask for human interaction when required.
6. **Secrets outside Git:** gateway keys, cookies, tokens, session state and proof material must not be committed or copied into documentation.
7. **Browser profiles are security boundaries:** stop only gateway-owned runtimes identified by explicit profile ownership.
8. **Loopback by default:** do not expose the API beyond localhost without a separately reviewed security design.
9. **Capability truth:** tools/search/files/vision/streaming are advertised only when independently accepted.
10. **No sensitive organizational data by default:** unofficial Web-chat transports are not automatically approved for SUMS or other sensitive workloads.
11. **No stress testing of personal Web accounts:** keep live acceptance bounded and conservative.
12. **Do not tag or release from a dirty worktree.**

## Runtime ownership

### ChatGPT Web

Uses the configured ChatGPT CDP/browser context. Ordinary user Chrome tabs are not assumed to be gateway-owned.

### Qwen Web

Owned runtime/profile:

```text
.runtime\qwen-profile
```

Runtime label:

```text
HWG-Qwen-Web-Controller
```

### Z.ai Web

Owned profile:

```text
.runtime\zai-profile
```

Dedicated CDP:

```text
127.0.0.1:9223
```

Runtime label:

```text
HWG-Zai-Web-SSE-Capture
```

Cleanup must use the owned profile path, not merely the URL `chat.z.ai`.

### DeepSeek Web

Uses the project-owned DeepSeek browser profile on CDP port `9226`. The 2026-09-12 controlled audit and KiloGate-WM smoke evidence supersede the earlier blocked-account state. Anti-abuse/circuit-breaker rules remain in force if suspension, CAPTCHA, or challenge evidence reappears.

## First operational checks

From PowerShell:

```powershell
cd D:\Code\mcp-web-bridge
.\service_manager.ps1 status
.\service_manager.ps1 config
Invoke-RestMethod http://127.0.0.1:5000/health
```

For authenticated endpoints, load the local runtime key without printing it:

```powershell
$GatewayKey = (Get-Content .\.env | Where-Object { $_ -like 'BRIDGE_API_KEY=*' } | Select-Object -First 1).Split('=',2)[1]
$Headers = @{ Authorization = "Bearer $GatewayKey" }

Invoke-RestMethod http://127.0.0.1:5000/ready -Headers $Headers
Invoke-RestMethod http://127.0.0.1:5000/modes -Headers $Headers
Invoke-RestMethod http://127.0.0.1:5000/v1/models -Headers $Headers
```

Never echo or copy `$GatewayKey` into shared output.

## Deterministic verification gate

Before committing code/config changes:

```powershell
.\.venv\Scripts\python.exe -m compileall -q main.py control_panel.py manage.py core adapters tests tools
.\.venv\Scripts\python.exe -m pytest -q
git diff --check
git status --short --branch
```

Current deterministic baseline verified on 2026-09-15:

```text
129 passed
```

The compile gate intentionally targets tracked source/test paths and excludes `.runtime/`, which contains ignored operational artifacts rather than release source.

Accepted 0.6.5 Kilo E2 evidence:

```text
Kilo -> hooshka/chatgpt-web -> KILO_HWG_CHATGPT_OK
Kilo --agent summary -> hooshka/zai:glm-5.3 -> KILO_HWG_ZAI_GLM53_OK
Kilo --agent summary -> hooshka/qwen:qwen3.8-max -> KILO_HWG_QWEN_MAX_OK
```

Do not run repeated live provider tests unless the change actually requires provider E2 validation.

## Main API surface

- `GET /health` — process/liveness identity
- `GET /ready` — provider readiness
- `GET /health/deep` — deeper runtime/provider diagnostics
- `GET /modes` — capability and transport provenance
- `GET /v1/models` — canonical routable models
- `POST /v1/chat/completions` — primary chat/stream endpoint
- `POST /v1/chat/code` — code-oriented compatibility endpoint
- `POST /v1/chat/conversation` — conversation continuity endpoint

See `docs/API_REFERENCE.md` and `docs/PRACTICAL_USAGE.md`.

## Hooshka integration boundary

Hooshka should consume operations equivalent to:

```text
health()
ready()
capabilities()
models()
chat(request)
chat_stream(request)
```

Hooshka should not import provider classes or know browser selectors, provider tokens, signatures, challenge details or session-storage structures.

See `docs/HOOSHKA_INTEGRATION_GUIDE.md`.

## If something fails

Use:

```text
docs/TROUBLESHOOTING_CURRENT.md
docs/OPERATIONS_RUNBOOK.md
```

Stop testing immediately on:

- account suspension or mute;
- repeated CAPTCHA/challenge;
- duplicate-submit evidence;
- uncontrolled browser spawning;
- secret exposure;
- unexpected cross-provider routing;
- unexplained provider enforcement.


### Current release status - 2026-09-25

- Release: `2.1.0` (E2 operational)
- - Evidence: `docs/evidence/HWG_2.1.0_PRODUCTION_RELEASE_EVIDENCE_20260925.md`
- Cutover, rollback/restore, production restart and exact stable-version local gates passed. E3 reliability is not claimed.
- Production cutover on port 5000 is complete; service identity is `HooshkaWebGateway`.
- E3 reliability is not claimed.

## Release and rollback

Current release:

```text
v2.1.0
```

Pre-canonical-migration rollback reference:

```text
rollback/pre-hooshka-web-gateway-migration
```

Pre-2.1 rollback reference:

```text
rollback/pre-2.1.0-rc1-cutover-20260925
```

For future risky changes, create a new rollback reference at the exact accepted SHA before migration/release work.

---

**Agent instruction:** Preserve this file as the primary repository discovery document. When the architecture, provider status, release baseline, service identity, or canonical documentation set changes, update this file in the same change set.
