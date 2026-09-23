# HWG Agent Authorization Gate — E1 Evidence — 2026-09-23

- Work item: `HWG-WORK-028`
- Version: `1.0.0-dev.7`
- Evidence level: **E1 — deterministic local evidence**
- Scope: execution authorization boundary for governed Agent Tools
- Production/E2/E3 claim: **none**

## Problem

The Agent Tool Registry already classified tools by risk and authorization mode, but the execution loop did not enforce those fields before dispatch. A future mutating tool could therefore have been exposed without a real server-side authorization gate.

## Implemented control

`core/agent_execution.py` now evaluates every tool descriptor before registry dispatch. READ_ONLY + `none` remains executable; missing descriptors, inconsistent non-read-only/no-auth descriptors, unknown authorization modes, untrusted authorization evidence, and out-of-scope tools fail closed.

A trusted `ToolAuthorizationContext` models policy, explicit human approval, and CAG evidence. The model/client request itself is not treated as authorization evidence.

## Deterministic verification

- Target authorization-policy tests: `9 passed`.
- Full deterministic suite after the change: `427 passed`.
- Full tracked-source `compileall`: PASS.
- `git diff --check`: PASS (line-ending warning only; no whitespace error).

Negative-path coverage includes: no trusted authorization, missing descriptor, CAG evidence requirement, and authorization scope mismatch. Positive coverage confirms scoped trusted CAG evidence permits the specifically authorized tool in the synthetic registry.

## Security properties

- Registry dispatch occurs only after authorization evaluation.
- Unknown/descriptorless tools fail closed.
- A non-read-only tool configured with `authorization_mode=none` fails closed.
- Authorization is scoped to named tools when `approved_tools` is populated.
- Evidence records expose the resulting authorization state.

## Remaining gap

No mutating production tool is enabled by this change. The Interactive Agent loop still has no trusted CAG/approval adapter wired into it; therefore future write/command/MCP actions remain blocked by default. Controlled E2 requires a real CAG decision/evidence path plus a bounded non-production side-effect test.
