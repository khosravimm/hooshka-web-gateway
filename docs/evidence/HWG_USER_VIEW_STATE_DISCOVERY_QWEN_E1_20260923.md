# HWG User-View State Discovery — Qwen E1

Date: 2026-09-23
Scope: Explorer Engine / Visual State Discovery
Evidence level: E1 live read-only

## Result
The Qwen runtime at `https://chat.qwen.ai/` was observed from the rendered user view, not inferred only from backend or DOM capability absence.

Visible page text: `Qwen is not available in your region.`

Explorer classification:
- user_view_state: `region_blocked`
- access_state: `BLOCKED`
- media capability conclusion: unverified; absence of file input must not be interpreted as unsupported while access is blocked.

## Capability added
`core.visual_discovery` now classifies visible states including region block, login required, challenge/CAPTCHA, rate limit, service error, loading, upload busy, ready and interactive-not-ready.

Screenshot capture now falls back to Chrome CDP `Page.captureScreenshot` when Playwright screenshot capture times out.

This state is included in the normal Discovery Runtime findings so future providers inherit the same observation path.
