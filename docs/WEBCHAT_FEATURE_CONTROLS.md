# Web Chat Thinking & Search Controls

Release: 0.7.1`r`nDate: 2026-09-16

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
| ChatGPT Web | `false` -> minimum available reasoning effort; `true` -> non-zero reasoning effort | ChatGPT composer Web search selection pill | authenticated E2 4/4 matrix PASS on 2026-09-16 |
| Qwen Web | frontend/backend `thinking` flag | frontend/backend `search` flag | authenticated E2 4/4 matrix PASS on 2026-09-16 |
| Z.ai Web | completion payload `features.enable_thinking`; effort `low/max` | completion payload `features.web_search` and `auto_web_search` | authenticated E2 4/4 payload matrix PASS on `zai:glm-5.3` on 2026-09-16 |
| DeepSeek Web | DeepThink control | Search control | authenticated E2 4/4 matrix PASS on 2026-09-16 |

## Important semantics

### ChatGPT

`thinking=false` means the lowest controllable reasoning effort exposed by the current ChatGPT Web UI. It does **not** prove that the upstream model performs zero internal reasoning.

### Fail-closed behavior

If a requested feature cannot be located, set, or verified, the provider raises `feature_control_failed` or an unsupported-feature error rather than silently continuing with an unknown state.

### Provider UI drift

These controls depend on provider Web Chat surfaces. Selector/payload drift is expected over time. Every provider implementation must verify the applied state before user content is submitted whenever the control is UI-driven.

## Evidence level

- Feature contract and persistence: E1 deterministic.
- Authenticated Thinking/Search matrix: E2 4/4 PASS for ChatGPT Web, Qwen Web, DeepSeek Web and Z.ai Web on 2026-09-16.
- Z.ai evidence is based on observed backend completion payload fields for `zai:glm-5.3`.
- ChatGPT `thinking=false` remains an effort-floor control, not a guarantee of zero hidden reasoning.
- Detailed matrix evidence is recorded in `docs/WEBCHAT_FEATURE_MATRIX_E2_2026-09-16.md`.
- No E3 reliability claim is made.
