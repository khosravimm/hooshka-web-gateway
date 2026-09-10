# Hooshka Web Gateway — Configuration Reference

Primary tracked configuration: `config.yaml`.

Runtime secrets belong in environment/runtime secret storage, not in `config.yaml`.

## Server

```yaml
server:
  host: 127.0.0.1
  port: 5000
  debug: false
```

`host` must remain loopback by default.

## ChatGPT Web

Canonical model: `chatgpt-web`.

Important fields:

- `cdp_url`
- `chatgpt_url`
- `adapter`
- `timeout`
- `long_text_chunk_size`

Current baseline uses a ChatGPT Web CDP/browser path and advertises tools only because the tool path has E2 evidence.

## Qwen Web

Canonical model: `qwen-web`.

Important fields:

- `transport_mode: browser_controller`
- `profile_dir: .runtime\qwen-profile`
- `runtime_label: HWG-Qwen-Web-Controller`
- `browser_channel: chrome`
- `headless`
- `launch_timeout`
- `first_event_timeout`
- `idle_timeout`
- `total_timeout`
- `requests_per_minute`

Keep concurrency conservative. Do not increase rate limits merely because local tests pass.

## Z.ai Web

Canonical model: `zai-web`.

Important fields:

- `base_url: https://chat.z.ai`
- `frontend_version`
- `runtime_label: HWG-Zai-Web-SSE-Capture`
- `profile_dir: .runtime\zai-profile`
- `cdp_url: http://127.0.0.1:9223`
- timeout/rate controls

The provider must use provider-owned frontend/session/signature/CAPTCHA state. Do not add code that reverse-engineers or bypasses anti-abuse proof.

## Governance

```yaml
governance:
  auth:
    enabled: true
  rate_limiting:
    enabled: true
  audit:
    enabled: true
```

Current per-provider conservative rate budgets in tracked configuration are:

- ChatGPT Web: 20 requests/minute
- Qwen Web: 12 requests/minute
- Z.ai Web: 6 requests/minute

These are local gateway ceilings, not claims that provider policy permits sustained use at those rates. Operational testing should remain significantly more conservative.

## Runtime credential

The service manager sources the gateway bearer credential from `.env` and injects it into the NSSM service environment.

Rules:

- `.env` must remain untracked.
- Never print the bearer key in shared logs.
- Rotate on suspected exposure.
- Do not reuse provider Web credentials as gateway credentials.

## Logs

Tracked config points to:

- application log: `logs/bridge.log`
- audit log: `logs/audit.log`

Audit retention is configured independently.

## Configuration change gate

After any config change:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
git diff --check
.\service_manager.ps1 restart
```

Then validate `/health`, `/ready`, `/modes`, and `/v1/models`.

Do not perform live provider smoke tests repeatedly unless the change actually requires them.
