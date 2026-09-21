# Logout Live Test — deepseek-web (2026-09-20)

Blocked item "logout endpoint needs a live test" — VERIFIED LIVE on the shared
single-window browser (CDP 9330). All calls read-only/cleanup by design;
secret hashes only (NG-ACC-002, HWG-CTRL-REQ-001).

## Procedure & results
1. Pre-check `GET /panel/api/providers/deepseek-web/session` → 200,
   `"authenticated": true`.
2. `POST /panel/api/providers/deepseek-web/logout {"confirm": true}` → 200:
   - CDP `Storage.clearDataForOrigin` on `https://chat.deepseek.com`
   - cookies 16 → 0, localStorage 21 → 0
   - audit event `provider_logout` logged (key_ref only, no secrets)
   - panel recorded `{"cleared": {...}}`
3. Post-check `GET .../session` → 200:
   `{"authenticated": false, "mode": "blocked_or_guest",
     "signals": {"login": true, "captcha": false, "suspended_or_muted": false}}`
4. `GET /health` → 200 across the transition; no restarts needed.

## Notes
- The deepseek-web session was a real owner-provided login; logout cleared it
  fully. Re-login required before deepseek-web S1 requests again (owner-driven,
  per ADR-003 manual session policy). chatgpt-web and zai-web untouched/unaffected.
- A provider-logout audit entry is written with `key_ref` + hash only; no
  plaintext/hash of the actual secret is persisted (verify-only hashes,
  NG-SEC-001).
- No fabricated success: Chrome DOM confirmed `authenticated=false` + login
  signal, and the audit trail records the exact event.

## Evidence files
- This report.
- `logs/audit.log` → `provider_logout` event with key_ref.
- `logs/bridge.log` → slot/browser lifecycle for deepseek-web.
