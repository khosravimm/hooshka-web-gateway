# HWG Agent Loop Governance — E2 Evidence

Date: 2026-09-22
Work item: HWG-WORK-028
Provider: deepseek-web
Runtime: http://127.0.0.1:5080

## Scope
This checkpoint hardens the generalized read-only Agent Tool Execution Plane without enabling mutating or command tools.

Implemented controls:
- configurable maximum agent steps
- cumulative loop time budget
- per-tool execution timeout
- duplicate tool-call detection
- bounded tool-result delivery
- cumulative structured evidence
- explicit terminal state
- read-only risk and authorization metadata

Mutating tools remain fail-closed.

## E1 verification
Targeted tests after the change: 13 passed.
Full repository suite: 411 passed in 12.34s.
Python compileall: passed.
git diff --check: passed.

## E2 scenario 1 — Drive inventory
User intent: identify drives and free space on D.
Observed tool: list_drives.
Execution state: ok.
Terminal state: completed.
Provider synthesis returned real C: and D: capacity/free-space values.

## E2 scenario 2 — System identity
User intent: inspect hostname, OS, architecture and Python runtime.
Observed tool: system_info.
Execution state: ok.
Terminal state: completed.
Provider synthesis reported Safe-Laptop, Windows 11, AMD64 and Python 3.13.6.

## E2 scenario 3 — TCP listeners
User intent: inspect TCP listening endpoints.
Observed tool: network_listeners with limit=100.
Execution state: ok.
Terminal state: completed.
Provider synthesis included the active 5080 and 5181 local listeners among other observed endpoints.

## Operational finding
The configured restart path is not currently reliable: runtime_orchestration.gateway_service is HooshkaHWGNGDevGateway, but that Windows service is not installed. The scheduled restart task therefore recorded state=failed and did not reload the 5080 process. For this E2 run, only the identified 5080 development main.py process was replaced manually; port 5000 was not touched.

This operational gap is separate from the Agent Tool Plane E2 result and remains open for runtime hardening.

## Final regression
After governance/manifest synchronization and contract-test update, the full suite was rerun: 411 passed in 11.61s. compileall, node --check for chat.js, and git diff --check produced no errors.
