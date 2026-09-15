# Web Chat Thinking & Search Controls

Release: 0.7.0  
Date: 2026-09-15

Hooshka Web Gateway exposes a normalized feature-control contract for Web Chat providers.

## Contract

Each provider has persistent defaults:

- `thinking: true|false`
- `search: true|false`

The defaults live under:

```yaml
providers:
  - id: <provider-id>
    config:
      feature_defaults:
        thinking: false
        search: false
      feature_controls:
        thinking: true
        search: true
```

A request may override either value:

```json
{
  "model": "qwen-web",
  "thinking": true,
  "search": false,
  "messages": [{"role": "user", "content": "Explain the result."}]
}
```

If an override is omitted, the provider default is used.

## API

Read current defaults and control availability:

```http
GET /v1/providers/<provider-id>/features
```

Persist new defaults:

```http
PUT /v1/providers/<provider-id>/features
Content-Type: application/json

{
  "thinking": false,
  "search": true
}
```

`GET /modes` also reports:

```json
{
  "features": {
    "defaults": {"thinking": false, "search": false},
    "controls": {"thinking": true, "search": true}
  }
}
```

## Control Panel

The Providers table exposes separate Thinking and Search switches for every provider. Changes are persisted to `config.yaml`.

The UI must not imply capability solely because a preference exists. `feature_controls` is the control-surface truth; `feature_defaults` is only the user's default preference.

## Provider mappings

| Provider | Thinking mapping | Search mapping | Evidence |
|---|---|---|---|
| ChatGPT Web | `false` -> minimum available reasoning effort; `true` -> non-zero reasoning effort | ChatGPT composer Web search selection pill | live control-only E2 PASS on 2026-09-15 |
| Qwen Web | frontend/backend `thinking` flag | frontend/backend `search` flag | existing E2 transport evidence + deterministic regression coverage |
| Z.ai Web | completion payload `features.enable_thinking`; effort `low/max` | completion payload `features.web_search` and `auto_web_search` | payload discovery E2; implementation regression covered; full search-result E2 remains reliability evidence work |
| DeepSeek Web | DeepThink control | Search control | implementation E1; E2 pending while the current project session/account is unavailable for authenticated feature retest |

## Important semantics

### ChatGPT

`thinking=false` means the lowest controllable reasoning effort exposed by the current ChatGPT Web UI. It does **not** prove that the upstream model performs zero internal reasoning.

### Fail-closed behavior

If a requested feature cannot be located, set, or verified, the provider raises `feature_control_failed` or an unsupported-feature error rather than silently continuing with an unknown state.

### Provider UI drift

These controls depend on provider Web Chat surfaces. Selector/payload drift is expected over time. Every provider implementation must verify the applied state before user content is submitted whenever the control is UI-driven.

## Evidence level

- Feature contract and persistence: E1 deterministic.
- ChatGPT control-only live toggle: E2.
- Qwen control path: E2 inherited from the existing browser-controller transport and prior feature verification.
- Z.ai payload shape: E2 observed on the authenticated Web Chat frontend; 0.7.0 wiring is E1 regression-tested and requires continued E2 monitoring.
- DeepSeek: E1 only until account access is restored and both states are retested.
