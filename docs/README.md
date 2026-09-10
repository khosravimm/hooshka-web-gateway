# Hooshka Web Gateway Ã¢â‚¬â€ Documentation Index

> Repository-level discovery starts at `../HOOSHKA_WEB_GATEWAY_START_HERE.md`. Agents and humans should read that file first.

**Release:** 0.6.4
**Canonical project:** `hooshka-web-gateway`
**Module:** `web_gateway`

## Recommended reading path

| Audience / task | Start here |
|---|---|
| First-time reader | `START_HERE.md` |
| Operator / service owner | `OPERATIONS_RUNBOOK.md` |
| Browser/runtime observability | `BROWSER_OBSERVABILITY.md` |
| API consumer | `API_REFERENCE.md` |
| Day-to-day examples | `PRACTICAL_USAGE.md` |
| Hooshka integrator | `HOOSHKA_INTEGRATION_GUIDE.md` |
| Provider engineer | `PROVIDERS.md` |
| Developer | `DEVELOPMENT_GUIDE.md` |
| Security reviewer | `SECURITY_GOVERNANCE.md` |
| Configuration change | `CONFIGURATION_REFERENCE.md` |
| Incident/debugging | `TROUBLESHOOTING_CURRENT.md` |
| Architecture review | `ARCHITECTURE_CURRENT.md` |
| Release handoff | `FINAL_REPORT_2026-09-10.md` |
| Kilo E2 evidence | `KILO_E2_EVIDENCE_2026-09-11.md` |

## Canonical current documents

- `START_HERE.md` Ã¢â‚¬â€ product orientation, current status and safe operating rules.
- `ARCHITECTURE_CURRENT.md` Ã¢â‚¬â€ current component boundaries, routing, transports, retry and evidence model.
- `BROWSER_OBSERVABILITY.md` Ã¢â‚¬â€ UI/frontend/backend/response evidence chain, drift detection and fail-closed model verification.
- `API_REFERENCE.md` Ã¢â‚¬â€ endpoint contract, authentication, request/response and error semantics.
- `PRACTICAL_USAGE.md` Ã¢â‚¬â€ PowerShell/Python/OpenAI-compatible examples and common operating scenarios.
- `CONFIGURATION_REFERENCE.md` Ã¢â‚¬â€ tracked config, provider fields, runtime credentials and change gate.
- `OPERATIONS_RUNBOOK.md` Ã¢â‚¬â€ start/stop/restart, health sequence, provider runtime ownership and incidents.
- `PROVIDERS.md` Ã¢â‚¬â€ provider capability matrix and provider-specific engineering notes.
- `SECURITY_GOVERNANCE.md` Ã¢â‚¬â€ trust boundaries, secrets, data governance, risk controls and incident classes.
- `HOOSHKA_INTEGRATION_GUIDE.md` Ã¢â‚¬â€ stable `web_gateway` contract for Hooshka.
- `DEVELOPMENT_GUIDE.md` Ã¢â‚¬â€ repository map, provider development workflow and release gates.
- `TROUBLESHOOTING_CURRENT.md` Ã¢â‚¬â€ current diagnostic playbook.
- `FINAL_REPORT_2026-09-10.md` Ã¢â‚¬â€ 0.5.0 release-level handoff.
- `EXPLICIT_MODEL_SELECTION_EVIDENCE_2026-09-10.md` Ã¢â‚¬â€ dynamic catalog/default routing evidence and current Qwen quota state.
- `KILO_E2_EVIDENCE_2026-09-11.md` Ã¢â‚¬â€ current Kilo CLI E2 evidence for ChatGPT and Z.ai plus Qwen auth blocker.

## Research, evidence and history

These documents remain authoritative for their specific evidence/history but may describe earlier version states:

- `TEST_EVIDENCE_2026-09-10.md`
- `EXPERIENCE_LOG.md`
- `LESSONS_LEARNED.md`
- `DEEPSEEK_ACCOUNT_SUSPENSION_INCIDENT_2026-09-10.md`
- `BACKEND_FIRST_PLAYBOOK.md`
- `UNIFIED_PROVIDER_ARCHITECTURE.md`
- `AWA_REUSE_AUDIT_2026-09-10.md`
- `TOOL_BANK_EXPERIENCE_MINING_2026-09-10.md`
- `TECHNOLOGY_EXPERIENCE_MATRIX_2026-09-10.md`
- `HOOSHKA_WEB_GATEWAY_MIGRATION.md`
- `RUNTIME_NAMING_REGISTRY.md`
- legacy `deployment-guide.md` and `troubleshooting.md`

When a historical document conflicts with a canonical current document, use the canonical current document and then verify against code/config.

## Evidence rule

- E0: source/research evidence
- E1: deterministic unit/synthetic/prototype evidence
- E2: real Web-chat end-to-end evidence
- E3: repeated predefined reliability evidence across independent windows

No capability should be described as proven beyond its recorded evidence level.
