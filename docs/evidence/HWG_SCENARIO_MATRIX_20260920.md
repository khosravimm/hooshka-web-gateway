# Scenario Matrix Evidence — controllers per webchat (live, 2026-09-20)

Gateway hwg-next-1.0.0 dev.2, owner monitoring live. Runner: scripts/scenario_probe.py.
S1 baseline | S2 thinking-on | S3 search-on | S4 stream | S5 long prompt | S6 long answer.

## chatgpt-web — 6/6 PASS
- S1 18s exact, features thinking=false/search=false
- S2 13s exact, thinking=true + thinking_effort_index=1 (null in S1)
- S3 15s, search=true (answer suffixed '@Web search')
- S4 12s stream [DONE] 14 chunks
- S5 15s exact 3-word answer on long prompt (chunks_sent=3)
- S6 27s long answer 4891 chars

## zai-web (glm-5.2) — 6/6 PASS (with notes)
- S1 110s exact (first attempt 240s timeout: transient model-switch turbulence)
- S2 40s exact, backend_features enable_thinking=true/effort max
- S3 85s exact, web_search=true + auto_web_search=true
- S4 21s stream [DONE] 24 chunks
- S5 33s exact long prompt
- S6 first attempt HTTP 500 'frontend reported an upstream error' (provider-side,
  fail-closed, no fabrication); retry 50s, 4321 chars PASS
- Speed variance 21–212s independent of thinking flag (server congestion).

## deepseek-web — 6/6 PASS
- S1 17s, S2 18s (thinking=true), S3 49s (search=true), S4 13s stream,
  S5 14s long prompt exact, S6 17s long answer 2524 chars
- Found+fixed during run: missing `logger` in deepseek_browser_transport.py
  (broke thinking path with 500); server restarted, S2 re-run green.
- No captcha/login/suspension signals in any run.
