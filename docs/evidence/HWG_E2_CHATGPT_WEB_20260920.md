# E2 Certification Evidence — chatgpt-web

- date: 2026-09-20
- provider: chatgpt-web (model chatgpt-web, enabled, priority 100)
- gateway: hwg-next-1.0.0 1.0.0-dev.2, http://127.0.0.1:5080
- browser: system Chrome, CDP http://127.0.0.1:9324, profile `.runtime-dev\chatgpt-profile`
- prompt: `Reply exactly: HWG_E2_OK` (thinking=false, search=false, no tools)
- script: `scripts/e2_provider.py --model chatgpt-web`
- results: models-200 PASS, providers-200 PASS, capabilities-200 PASS,
  completion-200 PASS (status=200 len=9, exact match), stream-done PASS
  (status=200, 18 chunks, [DONE]). RESULT 5/5.
- user certification: PASS (interactive, owner present 2026-09-20)
- level: E2 (single live success; E3 repetition pending)
