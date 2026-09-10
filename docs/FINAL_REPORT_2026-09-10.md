# Hooshka Web Gateway — Final Project Report

**Report date:** 2026-09-10
**Release baseline:** 0.5.0
**Canonical repository:** `khosravimm/hooshka-web-gateway`
**Local path:** `D:\Code\hooshka-web-gateway`
**Windows service:** `HooshkaWebGateway`
**Hooshka module id:** `web_gateway`

## 1. Executive summary

The former `mcp-web-bridge` research/implementation line has been consolidated into one governed project named **Hooshka Web Gateway**.

The gateway exposes one local OpenAI-compatible API and routes requests to Web-chat providers through explicit provider adapters. It is intended to become Hooshka's `web_gateway` module rather than being embedded directly into Hooshka orchestration code.

At the final acceptance window:

- ChatGPT Web: operational E2 for basic chat and existing tool-call path.
- Qwen Web: operational E2 for basic chat and stream compatibility through the browser backend controller.
- Z.ai Web: operational E2 for basic chat and stream compatibility through the browser backend controller.
- DeepSeek Web: implementation/research knowledge retained, but live E2 is blocked by the current account suspension state. No bypass is permitted.

The deterministic regression suite passed **54/54** tests after the canonical rename work.

## 2. Canonical identity

| Item | Canonical value |
|---|---|
| Product | Hooshka Web Gateway |
| Technical id | `hooshka-web-gateway` |
| Hooshka module id | `web_gateway` |
| Future Python namespace | `hooshka_web_gateway` |
| Repository | `khosravimm/hooshka-web-gateway` |
| Local path | `D:\Code\hooshka-web-gateway` |
| Windows service | `HooshkaWebGateway` |
| Local API bind | `127.0.0.1:5000` |
| Legacy repository id | `mcp-web-bridge` |
| Legacy service id | `WebLLMBridge` |

The legacy names are retained only where required for historical evidence or upgrade cleanup.

## 3. Architecture

```text
Hooshka / local clients
        |
        v
Hooshka Web Gateway
        |
        +-- OpenAI-compatible API
        |     /health
        |     /ready
        |     /modes
        |     /v1/models
        |     /v1/chat/completions
        |
        +-- Exact / fail-closed provider router
        |
        +-- Provider adapters
              |
              +-- chatgpt-web
              +-- qwen-web
              +-- zai-web
              +-- deepseek-web [account-state blocked]
```

Transport preference remains:

1. direct backend HTTP/SSE/WebSocket when safe and stable;
2. browser-context backend calls;
3. browser network/controller capture;
4. DOM interaction only as a last fallback.

No silent cross-provider fallback is allowed.

## 4. Provider status

| Provider | Final status | Transport / evidence | Accepted capability boundary |
|---|---|---|---|
| ChatGPT Web | Operational E2 | existing Web provider/CDP path | chat, stream compatibility, existing tool-call path |
| Qwen Web | Operational E2 | `browser_backend_controller` | chat, reconstructed stream, reasoning control |
| Z.ai Web | Operational E2 basic chat | `browser_backend_controller` | chat, reconstructed stream |
| DeepSeek Web | Live E2 blocked | account-state circuit breaker | E0/E1 research only until authorized account state is restored |

### ChatGPT Web

Canonical model id: `chatgpt-web`.

Important accepted behaviors include exact routing, OpenAI-compatible chat, tool-call normalization, commitment-aware retry boundaries, and no replay after ambiguous post-submit failure.

### Qwen Web

Canonical model id: `qwen-web`.

The provider uses Qwen's frontend controller/backend path rather than typing into the chat DOM. Final post-migration smoke returned the exact expected response `HWG_QWEN_FINAL_OK`.

Observed final metadata included:

- frontend version `0.2.91`;
- transport `browser_backend_controller`;
- outward streaming provenance `reconstructed`;
- session mode `guest`.

### Z.ai Web

Canonical model id: `zai-web`.

Research established that Z.ai completion traffic reaches a real backend SSE endpoint and uses provider-owned frontend signature/CAPTCHA state. The accepted implementation lets the official frontend own provider-specific proof/session behavior and consumes runtime/backend state without implementing CAPTCHA bypass.

Final post-migration smoke returned the exact expected response `HWG_ZAI_FINAL_OK`.

Observed final metadata included:

- frontend version `prod-fe-1.1.93`;
- transport `browser_backend_controller`;
- session mode `authenticated`;
- upstream model observed as `x-preview-l`.

Tools, search, vision and files remain disabled for Z.ai until separate E2 acceptance.

### DeepSeek Web

The current DeepSeek Web account entered a temporary provider-enforced suspension/mute state.

Confirmed facts:

- the Web UI displayed the temporary suspension;
- same-origin backend behavior was consistent with an account-local restriction;
- local test history showed automated completion traffic including short bursts before the restriction.

The exact provider risk signal is not publicly disclosed, so the project records only the following causal assessment:

- **confirmed:** provider account/risk-control enforcement;
- **plausible contributing factor:** automated high-frequency Web-backend traffic;
- **not proven:** any single request, VPN/IP condition, prompt, browser fingerprint or CAPTCHA event as the sole trigger.

DeepSeek live automated completion remains disabled for the restricted account. No account/IP rotation, CAPTCHA bypass, WAF bypass or credential-copy workaround is allowed.

## 5. Risk controls adopted from the DeepSeek incident

The following controls are now part of the Web-chat engineering policy:

- provider-specific rate budgets;
- concurrency 1 by default for unofficial Web transports unless higher concurrency is independently proven;
- no stress/load testing against personal Web accounts;
- immediate circuit breaker on suspension, mute, challenge or abnormal-account signals;
- bounded retries;
- no replay after the submission commitment boundary;
- session reuse where appropriate;
- no secret/token/cookie logging;
- no account/IP rotation to evade enforcement;
- no CAPTCHA/WAF bypass;
- separate E1 implementation evidence from live E2 acceptance;
- no E3/stability claim without repeated independent reliability windows.

## 6. Runtime naming and ownership

Bridge-owned runtime labels use the `HWG-` prefix.

| Runtime | Label |
|---|---|
| ChatGPT Web connection | `HWG-ChatGPT-Web-CDP` |
| Qwen controller | `HWG-Qwen-Web-Controller` |
| Z.ai runtime | `HWG-Zai-Web-SSE-Capture` |
| DeepSeek blocked state | `HWG-DeepSeek-Web-Frozen` |

Browser cleanup must identify ownership by dedicated profile path. A user's ordinary Chrome tab must never be closed merely because its URL points to one of the supported providers.

## 7. Final migration evidence

The canonical migration completed as follows:

- rollback ref created before migration: `rollback/pre-hooshka-web-gateway-migration`;
- local directory renamed from `D:\Code\mcp-web-bridge` to `D:\Code\hooshka-web-gateway`;
- GitHub repository renamed from `khosravimm/mcp-web-bridge` to `khosravimm/hooshka-web-gateway`;
- Git origin changed to the canonical repository;
- legacy Windows service `WebLLMBridge` removed;
- canonical Windows service `HooshkaWebGateway` installed and started;
- service executable paths now resolve under `D:\Code\hooshka-web-gateway`;
- listeners verified on localhost only;
- `/health` reports canonical service id `hooshka-web-gateway`;
- `/ready` reported ChatGPT Web, Qwen Web and Z.ai Web ready;
- `/modes` returned the three registered operational provider ids;
- post-migration live smoke passed for ChatGPT Web, Qwen Web and Z.ai Web.

Post-migration exact smoke results:

- ChatGPT Web: `HWG_CHATGPT_FINAL_OK` — PASS.
- Qwen Web: `HWG_QWEN_FINAL_OK` — PASS.
- Z.ai Web: `HWG_ZAI_FINAL_OK` — PASS.

## 8. Security posture

Current controls include:

- API bind restricted to `127.0.0.1`;
- API authentication enabled;
- runtime credential supplied from local runtime configuration/NSSM environment rather than tracked source;
- no credential values are intentionally recorded in documentation or commits;
- secret scan executed before the migration baseline;
- provider routing is exact and fail-closed;
- unsupported provider features are rejected rather than silently approximated;
- browser profiles are treated as security boundaries;
- provider-owned anti-abuse controls are not bypassed.

This gateway must not be used to send SUMS organizational/sensitive data through unofficial Web-chat providers unless a separate approved governance decision explicitly permits it.

## 9. Evidence level and limitations

This release is an **E2 operational baseline**, not an E3 reliability release.

Specifically:

- 54 deterministic tests passed at final code gate;
- live post-migration basic-chat smoke passed for the three enabled providers;
- earlier stream acceptance passed for Qwen and Z.ai;
- DeepSeek live E2 is blocked by account state;
- long-duration reliability, sustained concurrency and high-volume behavior have not been claimed;
- Web-provider frontend changes can break runtime discovery and therefore require drift detection and revalidation.

## 10. Hooshka integration contract

Hooshka should consume this project through a stable local API boundary rather than importing provider-specific implementation classes.

Recommended module contract:

- `GET /health` — process/liveness identity;
- `GET /ready` — provider runtime readiness;
- `GET /modes` — capabilities and transport provenance;
- `GET /v1/models` — canonical routable models;
- `POST /v1/chat/completions` — chat and stream compatibility.

The Hooshka orchestration layer should specify the canonical model/provider and should not know browser selectors, provider signatures, CAPTCHA details or session storage structure.

## 11. Next engineering priorities

1. Add `deepseek-web` as a fully tested provider after the current account state is legitimately restored.
2. Add drift probes for frontend build/module changes for Qwen and Z.ai.
3. Replace remaining legacy `BRIDGE_*` configuration variable names only through a compatibility migration, not a breaking rename.
4. Add provider-specific circuit-breaker telemetry and operational counters.
5. Define an E3 reliability gate with low-risk, predefined test windows.
6. Integrate `web_gateway` into Hooshka through its local API contract.
7. Keep tool/search/files/vision capabilities disabled per provider until each receives independent E2 evidence.

## 12. Final disposition

**Hooshka Web Gateway 0.5.0 is accepted as the canonical project identity and as an E2 baseline for three active Web-chat providers: ChatGPT Web, Qwen Web and Z.ai Web.**

DeepSeek Web is retained as a blocked provider workstream pending legitimate restoration of the current account state.

This report is the release-level handoff document for future Hooshka `web_gateway` integration.
