# Thinking A/B Evidence — zai-web (live, 2026-09-20)

Prompt (both arms): `Reply exactly: HWG_E2_OK`, model glm-5.2, search=false.

| arm | backend_features | elapsed | result |
|---|---|---|---|
| thinking=false | enable_thinking=false, reasoning_effort=low | 166s (audit latency_ms=165674) | 200, exact 9 chars |
| thinking=true | enable_thinking=true, reasoning_effort=max | 73s | 200, exact 9 chars |

Finding: the thinking flag IS applied and verified per-request
(provider_meta.backend_features), but speed does not follow the flag —
true/max was faster than false/low. Variance (73–212s incl. earlier E2 runs)
is server-side congestion, not client-controlled. DOM toggle hunt: the
DeepThink MAX pill is a disabled indicator; model menu disabled; no
clickable thinking toggle found in session.
