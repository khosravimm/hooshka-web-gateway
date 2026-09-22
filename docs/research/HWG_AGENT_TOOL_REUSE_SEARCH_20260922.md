# HWG Agent Tool Plane - Reuse / Search First Record

Date: 2026-09-22
Scope: HWG-WORK-028 / Governed Tool-Driven Agent Gateway

## Repository-native assets reused
- core/local_tools.py: current bounded local read/inspection tools.
- core/agent_execution.py: bounded loop, timeout, duplicate detection, evidence and terminal state.
- core/tool_allowlist.py: fail-closed allowlist semantics.
- core/tool_adapter.py: standard-to-provider tool adaptation.
- core/agent_boundary.py: existing CAG Action Candidate boundary.
- core/governance.py: authentication, rate limiting, audit and redaction.
- Existing Playwright browser/provider transports remain the browser foundation.

## Existing machine runtimes reused
- Git for Windows
- HWG Python virtual environment
- Node.js and npm
- PowerShell 7 and Windows PowerShell
- GitHub CLI with the existing authenticated account
- requests, PyYAML, psutil and pywin32 already present in the project environment

## External repository search observations
- OpenHands software-agent-sdk exposes mature Terminal and FileEditor tool patterns.
- Official Model Context Protocol repositories/SDKs exist and should be preferred later when MCP scope is approved.

## Decision
No new software/package was installed for this checkpoint.
HWG extends its own registry and adapters around already-installed OS/engineering runtimes.
MCP and other enterprise connectors remain outside the owner-approved scope for this checkpoint.
