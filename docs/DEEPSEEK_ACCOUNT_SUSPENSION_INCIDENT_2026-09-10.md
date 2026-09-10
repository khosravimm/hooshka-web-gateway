# DeepSeek Account Suspension Incident — 2026-09-10

## Status
The DeepSeek Web account visible in the controlled Chrome session is temporarily suspended until 2026-09-11 15:35 (as displayed by the provider UI). A same-origin `POST /api/v0/chat_session/create` returned HTTP 200 with application `code=40002` and no session id while the suspension was active.

## Evidence reviewed
- DeepSeek Web UI explicitly reports a temporary suspension for violation of usage rules.
- Official DeepSeek User Agreement permits suspension/cancellation for agreement violations and places responsibility for account use on the account holder.
- Official DeepSeek FAQ includes a dedicated item for temporary account suspension, but the public page does not disclose the exact detection signal that caused this account's suspension.
- Local PoC runtime log recorded 25 OpenAI-proxy completion requests on 2026-09-10. 23 occurred before 15:35 local. The activity included bursts of 5 requests in ~34 seconds around 13:28 and 8 requests in ~84 seconds around 14:49–14:50.
- The PoC uses an unofficial Web backend/session path rather than the documented DeepSeek API product.
- Community-maintained DeepSeek Web-to-API projects report that abnormal/high-frequency automated use can trigger provider risk controls. This is secondary evidence only, not an official statement of the exact rule that triggered this account.

## Cause assessment
**Confirmed cause class:** provider risk-control / usage-policy enforcement on the current Web account.

**Exact trigger:** not disclosed by DeepSeek and therefore not proven.

**Most plausible contributing factor:** automated Web-backend traffic pattern from the local PoC, especially short request bursts and repeated scripted completion calls. The timing is consistent with the suspension, but correlation is not proof.

We do **not** attribute the suspension to prompt content, VPN/IP, browser automation, or any individual request because the available evidence is insufficient.

## Prevention controls
1. **Suspension circuit breaker:** any provider response/UI state indicating mute, suspension, challenge, or abnormal-account state immediately disables automated calls for that account.
2. **No evasion:** do not rotate accounts/IPs, bypass CAPTCHA/WAF, or copy unrelated browser credentials to continue service after provider enforcement.
3. **Low-rate Web budget:** Web-chat automation uses a conservative provider-specific request budget with jitter and enforced spacing; no burst/stress tests against personal Web accounts.
4. **Concurrency = 1 by default** for unofficial Web-chat transports until the provider is independently proven tolerant of more.
5. **Reuse active sessions** instead of repeatedly creating/deleting sessions when possible.
6. **Bounded retries only:** retry transient transport failures with capped attempts; never replay after the message submission commitment boundary.
7. **Account-state classification before retry:** account-local errors (mute/suspension/auth/challenge) are terminal for that account and must not be treated like network failures.
8. **Separate research and reliability testing:** E2 acceptance uses a small predefined test set. Load/stress testing is prohibited against personal Web accounts.
9. **Prefer provider-supported API for sustained automation** when policy-compliant automation is required; Web-chat adapters remain research/compatibility transports.
10. **No secret extraction/copying from personal browser storage** as a bootstrap shortcut.
11. **Evidence logging without credentials:** retain timestamps, endpoint class, status, error class, and attempt count; never log authorization tokens/cookies.
12. **Human review before re-enabling** an account after a suspension expires.

## Engineering decision
DeepSeek Web normal-completion E2 is blocked by the current account state. Development may continue at E0/E1 using protocol fixtures and local parsers, but no further live automated completion attempts will be made on this account during the suspension window.
