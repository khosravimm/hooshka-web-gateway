# Single-Window Migration Evidence (NG-BRW-001 / CTRL §1) — 2026-09-20

- Design: `docs/architecture/ADR-003-shared-window.md`
- Backup: `.runtime-dev-backup-20260920/` (3 profiles, bit-identical pre-migration)
- Shared runtime: ONE Chrome (1 browser process), CDP http://127.0.0.1:9330,
  profile `.runtime-dev\shared-profile`; old CDPs 9323/9324/9326 DOWN
- Config: `shared_browser.enabled=true`; all 3 enabled providers share
  cdp_url+profile (inventory duplicate-port rule relaxed only for this case)
- Tabs observed live in the single window: chatgpt.com conversation,
  chat.z.ai home, chat.deepseek.com conversation
- Traffic verified through the shared window (S1 each, exact match):
  chatgpt 16s, zai 125s (glm-5.2), deepseek 15s
- Isolation measured live (per-origin jars in one window):
  chatgpt.com 16 cookies/31 LS keys; chat.z.ai 16/21; chat.deepseek.com 3/35
- Rollback: set `shared_browser.enabled=false`, restore old cdp/profile values
  (CHANGELOG), relaunch per-provider chromes from backup. Production (5000) untouched.
- Known exception: same-provider multi-account needs separate windows
  (stock-Chrome jar limitation) — see ADR-003.
