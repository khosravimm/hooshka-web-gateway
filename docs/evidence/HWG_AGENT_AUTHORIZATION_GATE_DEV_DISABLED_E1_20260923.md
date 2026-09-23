# HWG Agent Authorization Gate ? Develop Disabled Evidence

Date: 2026-09-23
Scope: HWG 1.0.0-dev.7 / WORK-028
Evidence grade: E1

## Decision
The Authorization Gate remains implemented, but the HWG Next development configuration explicitly disables enforcement so agent/tool development is not blocked by an out-of-scope approval subsystem.

## Configuration
`agent_tools.authorization_gate_enabled: false` in the development `config.yaml`.

When disabled, tool execution evidence records `authorization_state=disabled_by_configuration`. The gate code, authorization context, risk metadata, and fail-closed behavior remain available for later controlled environments.

## Verification
- Targeted Agent policy/registry/interactive tests: 20 passed.
- Full deterministic test suite: 428 passed.
- `compileall -q main.py core`: PASS.
- `git diff --check`: PASS.

No claim is made that CAG or any external authorization service was tested or implemented.
