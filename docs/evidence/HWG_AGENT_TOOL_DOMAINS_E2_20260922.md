# HWG Agent Tool Domains — E1/E2 Evidence — 2026-09-22

## Scope
Owner-approved scope only: Native HWG, Native OS, Existing Engineering Runtime, GitHub, REST/OpenAPI.
No MCP, Wazuh/Zabbix, DB, Cloud, or new external software/package was installed.

## Reuse/Search First
Reused existing HWG: local tool plane, bounded agent loop, fail-closed allowlist, audit/governance, Playwright/provider transports.
Reused installed runtimes: Git for Windows, Python 3.13.6 project venv, Node 24.11.0, npm 11.6.1, PowerShell 7.6.6, GitHub CLI 2.96.0.
GitHub CLI was already authenticated; token material was not persisted into HWG tool results.

## Implementation
Canonical Tool Contract added with risk class, authorization mode, source, JSON input schema, and MCP-style annotations.
Canonical AgentToolRegistry now aggregates 38 active read-only/diagnostic tools.
Backends: local filesystem/host, Windows/system, engineering/Git/runtime, GitHub CLI/API, REST/OpenAPI.
Mutating/execution/destructive actions remain fail-closed pending governed authorization/CAG integration.

## E1
Targeted suite after compatibility fixes: 20 passed.
Final full regression after REST hardening and exposure-boundary test: 419 passed in 13.29s.
Python compileall completed without errors.

## Direct backend evidence
Registry count: 38 tools.
GitHub repo metadata for khosravimm/hooshka-web-gateway returned successfully through authenticated gh API.
REST GET to http://127.0.0.1:5080/health returned HTTP 200.
OpenAPI inspection of /apispec.json identified Swagger 2.0 and 9 operations.
Runtime inventory detected Git 2.51.2, Python 3.13.6, Node 24.11.0, npm 11.6.1, PowerShell 7.6.6, GitHub CLI 2.96.0.

## E2 Agent Mode
Development runtime 127.0.0.1:5080 was reloaded without touching port 5000.
DeepSeek Agent Mode exposed 38 tools.
Scenario 1: model selected github_repo_info; execution_state=ok, source=github_cli, risk=READ_ONLY, terminal=completed.
Scenario 2: model selected openapi_inspect for local HWG spec; execution_state=ok, source=rest_openapi, risk=READ_ONLY, terminal=completed.

## Remaining boundary
This checkpoint does not claim write/shell/service-control/Git mutation/HTTP mutation capability.
Those actions remain intentionally unavailable until the authorization/CAG execution path is integrated and verified.
