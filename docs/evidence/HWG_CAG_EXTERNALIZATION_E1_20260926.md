# HWG CAG Externalization ? E1 Evidence

Date: 2026-09-26
Build: `2.1.1-dev.cag-externalized.20260926-1342`
Scope: HWG Dev runtime and contracts

## Owner decision

CAG is not an HWG subsystem. Any caller that needs CAG owns that workflow externally. HWG must not call, embed, infer, or enforce CAG.

## Implemented

- Removed `core/agent_boundary.py` from active code.
- Removed request-side Hooshka/CAG prompt injection from `core/mcp.py`.
- Removed response-side command/code filtering and Action Plan/CAG replacement.
- Removed streaming CAG boundary and Gateway-to-CAG Action Candidate registration from `main.py`.
- Removed `ToolAuthorizationMode.CAG` and CAG-specific authorization evidence fields.
- Retained generic HWG authorization modes: `none`, `policy`, `approval`.
- Marked historical 0.7.20 and 0.7.21 CAG-in-HWG operational documents superseded.
- Added regression contract `tests/test_gateway_cag_externality.py`.

## Verification

Targeted architecture/authorization/version tests: **25/25 PASS**.

Full HWG suite after Dev restart: **650/650 PASS**.

Dev meta after restart: `2.1.1-dev.cag-externalized.20260926-1342`.
Production remained unchanged at `2.1.0 / 7492991`.

## Remaining E2

The clean Kilo/VS Code mission must be repeated on this build with no gateway code changes during the run. The first attempt after externalization was blocked by a real DeepSeek `LOGIN_REQUIRED` state, not by CAG.
