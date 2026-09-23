# HWG Public Cancellation + Panel Refresh — E2

Date: 2026-09-24
Scope: HWG-WORK-009 / HWG-WORK-025
Evidence level: E1 + E2

## Implemented
- `POST /v1/chat/cancel` exposes the existing provider cancellation hooks.
- Provider can be supplied explicitly or resolved from `conversation_id`.
- Provider/conversation mismatch fails closed.
- Python SDK exposes `cancel(...)`.
- TypeScript SDK exposes `cancel(...)`.
- OpenAPI compatibility manifest now publishes public cancellation as normalized.

## DeepSeek E2
A long DeepThink request was started on the live Dev runtime.
The first probe showed the old cancel hook could not identify the visual Stop state.
User-view observation then showed the composer primary button transition from disabled Send/loading to an enabled square Stop control.

After state-aware remediation, `/v1/chat/cancel` returned HTTP 200 with:
- `supported=true`
- `attempted=true`
- `cancelled=true`
- `clicked=true`
- `method=composer_primary_stop`

This is provider-side cancellation evidence, not only local HTTP abort.
## Request lifecycle normalization
A first E2 attempt on an earlier live build clicked Stop but the blocking request later surfaced the legacy provider-timeout envelope. The current build was reloaded and re-tested after cancellation-state propagation was wired into the DeepSeek transport.

Final live result:
- cancel API: HTTP 200, `cancelled=true`
- original request: HTTP 409, `type=generation_cancelled`
- `commitment_state=committed`
- `retry_allowed=false`
- no hidden replay

WORK-009 remains PARTIAL only because explicit Profile/Account targeting is still open.

## Panel refresh
Control Plane Embedded Chat Stop now calls `/v1/chat/cancel` and then aborts the local fetch.
UI release version remains synchronized at `1.0.0-dev.7`; a separate build marker `20260924-0105` was added to avoid a false release bump.
Static assets use cache-busting build query parameters.

Live panel verification on Dev:5080:
- UI header: `1.0.0-dev.7 · 20260924-0105`
- ATTACH: present and enabled for certified DeepSeek media capability
- Stop: present
- chat.js source: `/panel/assets/chat.js?b=20260924-0105`
