# E2 Certification Evidence — zai-web

- date: 2026-09-20
- provider: zai-web (model zai-web, enabled, priority 80)
- gateway: hwg-next-1.0.0 1.0.0-dev.2, http://127.0.0.1:5080
- browser: system Chrome, CDP http://127.0.0.1:9323, profile `.runtime-dev\zai-profile`
- first attempt: FAIL — `Z.ai runtime stores not found` (fresh profile, no login).
  Owner logged in manually in the open dev browser, then retry.
- prompt: `Reply exactly: HWG_E2_OK` (thinking=false, search=false, no tools)
- results: models-200 PASS, providers-200 PASS, capabilities-200 PASS,
  completion-200 PASS (status=200 len=9, exact match), stream-done PASS
  (status=200, 88 chunks, [DONE]). RESULT 5/5.
- user certification: PASS (interactive, owner present 2026-09-20)
- level: E2 (single live success; E3 repetition pending)
