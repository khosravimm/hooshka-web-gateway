# HWG Provider Tool Discovery + Profile Persistence — E2

Date: 2026-09-22
Scope: HWG-WORK-028 / Provider Discovery qualification

## Change
Provider Discovery now includes a governed active tool-call capability probe during `/explore`.
The probe defines one synthetic function `hwg_tool_capability_probe`, forces exactly that function, verifies the returned marker, and never executes the function.

The result is attached to the Discovery Run as `findings.exploration.tool_capability_probe` and persisted to the NG Provider Profile under `tool_capabilities` with bounded history.
Only allow-listed non-secret fields are persisted; the random marker and raw prompt are not stored.

## Automated evidence
- Targeted discovery/profile/tool-probe suite: 23 passed before final additions.
- Full regression before final additions: 421 passed.
- Negative probe test added: plain-text response must not be inferred as tool support.
- Integration source test added: Discovery Explore must invoke probe and profile persistence.

## Live E2 — DeepSeek
Official Discovery API flow executed against development runtime on port 5080:
1. Create Discovery Run.
2. Attach research evidence.
3. Capture baseline → `EXPLORATION_READY`.
4. Explore → active tool qualification probe.

Run ID: `2e7113fc-22c7-435a-8a39-842db20ba4e8`

Observed tool probe:
- provider: `deepseek-web`
- model: `deepseek-web`
- tested: true
- supported: true
- protocol_valid: true
- marker_match: true
- execution: `not_executed`
- reason: `forced_tool_call_valid`
- evidence_level: E2

Profile persistence:
- profile_id: `deepseek-web:default`
- persisted: true
- profile field: `tool_capabilities.latest`
- bounded history present under `tool_capabilities.history`

The overall Discovery Run remained at E1/UPDATE_CANDIDATE because tool qualification is only one E2 sub-evidence item; it does not automatically certify the whole provider profile.
