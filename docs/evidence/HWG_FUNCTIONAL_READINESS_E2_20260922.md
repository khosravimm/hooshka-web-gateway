# HWG Functional Readiness — E2 Evidence

- Date: 2026-09-22
- Scope: `HWG-WORK-003` / NG-RDY-001..003
- Runtime: Development `127.0.0.1:5080`
- Application line: `1.0.0-dev.6`
- Readiness contract: `1.1.0`
- Evidence class: E1 + scoped E2

## Readiness contract

A Provider is not READY merely because it is registered, its process exists, or CDP responds. Functional readiness now requires this ordered chain:

1. `runtime_cdp`
2. `page_interactive`
3. `access_auth`
4. `model_state`
5. `feature_state`
6. `functional_probe`

Only a successful bounded exact-token round-trip may produce `READY`.
## DeepSeek live functional probe

The first strict probe failed closed at `FEATURE_INVALID`: DeepThink was observed but Search was missing from Discovery output. A read-only DOM inspection showed that Search was actually present as a sibling `DIV.ds-toggle-button` with `tabindex=0`.

Root cause was internal Discovery drift: `discovery_engine.py` maintained a second DOM enumerator that deduplicated controls using a truncated `outerHTML` prefix. Similar sibling controls could collapse into one record. The duplicate enumerator was removed; Discovery and Readiness now reuse the canonical `core/control_discovery.py` enumerator.

After that correction, DeepSeek passed all six stages. Both `thinking_toggle` and `search_toggle` were observed. The selected canonical model was `deepseek-web`. The bounded probe explicitly requested `thinking=false` and `search=false`; provider evidence confirmed both states were applied. The exact-token response matched byte-for-byte, producing `READY` with a 300-second TTL.

`GET /ready` then returned HTTP 200 with `mode=functional_cache`, proving that readiness is derived from current bounded functional evidence rather than process/CDP registration alone.
## Qwen negative-path validation

Qwen CDP and page were reachable, but structural access classification returned `BLOCKED / region_restriction`. Readiness stopped after `runtime_cdp`, `page_interactive`, and `access_auth`; model, feature, and functional-probe stages were not executed. No message was sent to Qwen.

## Failure classification

The readiness contract distinguishes `PAGE_NOT_INTERACTIVE`, `MODEL_INVALID`, `FEATURE_INVALID`, `FEATURE_APPLY_MISMATCH`, `SILENCE`, `INVALID_RESPONSE`, `STALLED_OR_TIMEOUT`, `AUTH_LOST`, `BLOCKED`, and `SERVER_OR_ACCOUNT_ERROR`. Logout or a later non-authenticated account state invalidates cached READY evidence immediately.

## Scope limits

This is scoped E2 for the current Provider/Account readiness semantics. It is not E3 reliability and does not certify every Provider, account, model, feature combination, or repeated-window condition.

## Deterministic validation

- Targeted readiness/discovery regression checks: PASS.
- Full deterministic suite: **338 passed**.
- `compileall`: PASS.
- JavaScript syntax: PASS.
- `git diff --check`: PASS.
