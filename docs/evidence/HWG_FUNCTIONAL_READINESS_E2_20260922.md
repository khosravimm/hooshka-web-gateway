# HWG Functional Readiness — E2 Evidence

- Date: 2026-09-22
- Scope: `HWG-WORK-003` / NG-RDY-001..003
- Runtime: Development `127.0.0.1:5080`
- Application line: `1.0.0-dev.6`
- Evidence class: E1 + scoped E2

## Readiness contract

A Provider is not READY merely because it is registered, its process exists, or CDP responds. Functional readiness requires these ordered stages:

1. `runtime_cdp`
2. `access_auth`
3. `model_state`
4. `feature_state`
5. `functional_probe`

Only a successful bounded exact-token functional round-trip may produce `READY`.

## DeepSeek live functional probe

The readiness cache was removed before the test. `/ready` initially returned HTTP 503 because no current functional evidence existed.

DeepSeek then passed all five stages. The selected canonical model was `deepseek-web`; model discovery returned the same model. Default Thinking/Search were both off while both controls were available. The exact-token prompt returned the expected token byte-for-byte, so the record became `READY` with a 300-second TTL.

After this record was saved, `/ready` returned HTTP 200 with `mode=functional_cache` and DeepSeek `ready=true`.

## Qwen negative-path validation

Qwen CDP was reachable, but structural access classification returned `BLOCKED / region_restriction`. Readiness stopped after `runtime_cdp` and `access_auth`; model, feature and functional-probe stages were not executed. No message was sent to Qwen.

## Cache and invalidation

Readiness records are TTL-bounded and are read by `/ready` without live provider calls. Logout or any later non-authenticated session state invalidates previous readiness immediately. UI and Provider payloads expose Browser readiness and Functional Readiness as separate states.

## Scope limits

This is scoped E2 for current functional readiness semantics. It does not constitute E3 reliability or certify every model/feature combination; those require their own matrix and repeated evidence.
