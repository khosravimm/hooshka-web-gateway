# AWA Reuse Audit — 2026-09-10

Source project: `D:\Code\ai-web-adapter`
Target project: `D:\Code\mcp-web-bridge`

## Purpose
Reuse practical Web-LLM gateway experience without copying assumptions or claiming evidence that was not reproduced in the target repository.

## Source status observed
AWA had a clean working tree when inspected and contains extensive ADRs, experience logs, tests, Responses/tool-round-trip work, and browser/provider architecture. Its current `npm test -- --runInBand` run during this review was **not fully passing**: a regression expected an unsafe HOST configuration to fail closed, but the process stayed alive. Therefore AWA is treated as a knowledge/evidence source, not as a currently verified implementation to import wholesale.

## Reuse matrix

| AWA finding / decision | Target action | Target evidence |
|---|---|---|
| ADR-021 commitment-aware attempt state | Added `submission_started` boundary; post-submit failures do not replay | E1 regression: post-submit 1 attempt, pre-submit may retry once |
| Broad no-tool retry over-fires in live use | Removed broad auto-review design | E1 + E2 |
| Strong-signal-only tool retry | Added explicit-tool, tool-mention, sandbox/substitution, EN/FA refusal signals | E1 tests + live explicit/2+2/WSL cases |
| ADR-023 provider-local transport selection | Exact canonical model routing; no cross-provider wildcard/fallback | E1 routing tests + live unknown model/provider 400 |
| ADR-024 incremental streaming boundary | Removed HTTP-layer async-stream collection; queue pass-through | Code invariant + live SSE tool-call; delayed synthetic HTTP timing test still desirable |
| Streaming provenance must be explicit | Added capability `streaming_mode`; ChatGPT DOM is `buffered` | E1/runtime introspection after restart |
| ADR-025 origin/session isolation | Recorded as mandatory requirement for future providers | Design only; not fully implemented yet |
| ADR-026 config precedence and secret boundary | Runtime API secret moved out of tracked YAML; loopback default | E1/current runtime evidence |
| Responses API / Codex tool round-trip experience | Added to planned compatibility surface | Design only; implementation pending |
| Push known deterministic context vs uncertain pull | Recorded as optional provider strategy | Design only; no generic automatic push implemented |

## Findings not copied directly

- AWA provider-specific selectors, browser profile layout, internal tool names, and retry implementations were not copied blindly.
- AWA's current unsafe-HOST test failure means its origin/config enforcement code must be independently reviewed before any direct reuse.
- AWA's historical E2 results do not count as E2 evidence for this repository.

## Result
AWA materially improved the target design. The highest-value transfer was not code but **failure knowledge**: commitment boundaries, strong-signal-only tool correction, exact provider-local routing, and the fact that streaming can be accidentally re-buffered above the provider layer.

All transferred behaviors that currently affect ChatGPT runtime have independent regression or live evidence in `mcp-web-bridge`. Remaining design-only items are explicitly labeled as such.
