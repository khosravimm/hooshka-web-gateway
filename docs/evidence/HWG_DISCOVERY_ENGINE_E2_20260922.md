# HWG Discovery Engine Governed E2 Evidence — 2026-09-22

- Evidence ID: `HWG-EVID-DISC-E2-20260922`
- Product version: `1.0.0-dev.5`
- Discovery Engine: `2.1.0-dev.1`
- Provider: `deepseek-web`
- Run ID: `33f08b91-9fca-4d04-84d9-61d7a78b65f0`
- Final state: `CERTIFIED`
- Evidence level: `E2`
- Execution authority: `automated_validation`

## Governed lifecycle exercised

The live run executed Research, access-aware Baseline, read-only Exploration, Synthesis, Update Candidate review, Certification, and a real exact-token provider round-trip. Baseline classified the live DeepSeek session as authenticated before Exploration was allowed.

Exploration produced 13 drift entries. The candidate was accepted only for certification of the observed state; no Provider Profile or production configuration was mutated automatically.

## Functional certification

The certification probe used the deterministic self-use transport qualification harness. A random nonce marker was submitted through the current DeepSeek provider adapter and the returned assistant text was compared by exact string equality. The probe returned `passed=true` and `allowed=true` and generated a transport-bound evidence record.

## Browser Behavior Lab cross-provider validation

The Behavior Lab is now live-validated on two providers. DeepSeek hover observation captured before/after state plus bounded network metadata without click or prompt submission. A second live validation on Z.ai first exposed selector drift: the historical GLM-5.3 model-selector locator was no longer visible. Fresh discovery identified the current visible selector `#model-selector-glm-5_2-button`; a hover probe then completed successfully with `aria="Select a model"`, `expanded=false` before/after, and no network/WebSocket/SSE side effect.

This validates that stale historical selectors are not silently trusted and that current Discovery evidence can drive bounded Behavior Lab observation.

## Access gating evidence

The same development window validated the access state machine against live runtimes: DeepSeek classified `AUTHENTICATED` and advanced to `EXPLORATION_READY`; Qwen classified `BLOCKED / region_restriction` and remained blocked from Exploration. No regional restriction bypass was attempted.

## Residual observation

After the successful DeepSeek E2 run, Python emitted ignored Windows Proactor/asyncio transport destructor warnings during interpreter shutdown. The governed run had already reached `CERTIFIED/E2`, the exact-token probe had passed, and the process exited with code 0. This cleanup warning is recorded as separate engineering debt and is not treated as provider/certification failure.

This record does not claim E3 reliability, cross-provider certification, or release-candidate readiness.
