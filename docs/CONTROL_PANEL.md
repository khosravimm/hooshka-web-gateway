# Hooshka Web Gateway Control Panel

Release: 0.7.2  
Date: 2026-09-16

The local management UI is available at:

```text
http://127.0.0.1:5000/panel/
```

## Safe operation rule

Use a dedicated browser tab or an isolated temporary browser profile for panel validation. Do not reuse provider Web Chat tabs or user work tabs for panel testing.

## Current management surfaces

- Overview dashboard with service status, provider count, ready-provider count, active sessions and request volume.
- Version/commit/branch/evidence metadata in the header.
- Per-provider runtime/CDP readiness in Overview.
- Provider table with enabled state, runtime readiness, CDP URL, capability chips, supported models and Thinking/Search defaults.
- Persistent Thinking/Search default controls for each provider.
- Sessions, API keys, service actions, logs and config tabs.

## Runtime readiness semantics

`/panel/api/providers` checks each provider's configured `cdp_url` with `/json/version` and reports:

- `ready`: CDP endpoint answered and exposed a debugger WebSocket.
- `unavailable`: endpoint did not answer within the local timeout.
- `not_applicable`: provider has no dedicated CDP URL.

This readiness is separate from provider capability. A provider can be configured and enabled while its browser runtime is down.

## Panel metadata API

```http
GET /panel/api/meta
```

Returns:

```json
{
  "version": "0.7.2",
  "commit": "<short-sha>",
  "branch": "master",
  "evidence": "E2 Thinking/Search 4x4"
}
```

## Validation evidence

Validated on 2026-09-16 with an isolated temporary Chrome profile, not by reusing user tabs:

- Panel title rendered correctly.
- Header exposed version, commit, branch and evidence.
- Ready Providers card rendered.
- Provider Runtime Readiness section rendered.
- Providers tab showed all four Web Chat providers and their CDP URLs.
- Service status and `/panel/api/providers` reported all four CDP runtimes ready.

## Known debt

The panel still loads Tailwind, Chart.js and FontAwesome from CDNs. This is acceptable for the local operator panel baseline, but production hardening should bundle these assets locally and remove CDN dependency.
