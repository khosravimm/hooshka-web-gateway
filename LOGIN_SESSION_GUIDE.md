# Hooshka Web Gateway - Official Login and Session Persistence Guide

**Policy baseline:** 0.6.4

This repository does not store provider usernames, passwords, cookies, tokens, authorization headers, CAPTCHA proof, or browser-storage secrets in source control.

The official login model is:

```text
human login through the provider's official website
        |
        v
dedicated provider browser profile
        |
        v
Hooshka Web Gateway reuses that profile/session
        |
        v
completion allowed only when session_status.authenticated == true
```

Guest sessions are disabled by policy for Web-chat providers used by Hooshka Web Gateway.

## Mandatory rules

1. Do not use Qwen, Z.ai, DeepSeek, ChatGPT or any other Web-chat provider in guest mode.
2. Do not paste passwords or one-time codes into code, docs, logs or issue reports.
3. Do not extract provider cookies/tokens from browser storage into repo files.
4. Do not print provider authorization headers.
5. Do not bypass CAPTCHA, WAF, risk controls or account suspension.
6. Use the provider's official login UI only.
7. Persist login state only in the dedicated browser profile owned by the gateway.
8. If the session expires, stop automation and re-login manually through the official UI.

## Dedicated profiles

Qwen Web profile:

```text
D:\Code\hooshka-web-gateway\.runtime\qwen-profile
```

Z.ai Web profile:

```text
D:\Code\hooshka-web-gateway\.runtime\zai-profile
```

These profiles are local runtime state and must not be committed.

## Current config enforcement

`config.yaml` must contain:

```yaml
qwen-web:
  require_authenticated: true

zai-web:
  require_authenticated: true
```

The actual tracked YAML is provider-list based, but the effective policy is the same:

```yaml
- id: qwen-web
  config:
    require_authenticated: true

- id: zai-web
  config:
    require_authenticated: true
```

## Qwen login procedure

1. Stop the gateway service if it is currently using the Qwen profile:

```powershell
cd D:\Code\hooshka-web-gateway
.\service_manager.ps1 stop
```

2. Open Chrome manually with the dedicated Qwen profile:

```powershell
& "C:\Program Files\Google\Chrome\Application\chrome.exe" `
  --user-data-dir="D:\Code\hooshka-web-gateway\.runtime\qwen-profile" `
  --no-first-run `
  https://chat.qwen.ai/
```

3. Login through the official Qwen UI.

4. Confirm that the page shows the logged-in account state, not guest state.

5. Close that Chrome window.

6. Start the gateway:

```powershell
.\service_manager.ps1 start
```

7. Verify readiness:

```powershell
$GatewayKey = (Get-Content .\.env | Where-Object { $_ -like 'BRIDGE_API_KEY=*' } | Select-Object -First 1).Split('=',2)[1]
$Headers = @{ Authorization = "Bearer $GatewayKey" }
Invoke-RestMethod http://127.0.0.1:5000/ready -Headers $Headers
```

`qwen-web` should not be treated as usable until it is authenticated. If Qwen returns guest state, the gateway must reject completion with `auth_required`.

## Z.ai login procedure

1. Stop the gateway service only if login conflicts with the owned runtime:

```powershell
cd D:\Code\hooshka-web-gateway
.\service_manager.ps1 stop
```

2. Open Chrome manually with the dedicated Z.ai profile:

```powershell
& "C:\Program Files\Google\Chrome\Application\chrome.exe" `
  --user-data-dir="D:\Code\hooshka-web-gateway\.runtime\zai-profile" `
  --no-first-run `
  https://chat.z.ai/
```

3. Login through the official Z.ai UI.

4. Complete any provider challenge manually if the site asks for it.

5. Confirm that the account menu shows the intended logged-in account.

6. Close that Chrome window.

7. Start the gateway:

```powershell
.\service_manager.ps1 start
```

8. Verify readiness and model catalog:

```powershell
$GatewayKey = (Get-Content .\.env | Where-Object { $_ -like 'BRIDGE_API_KEY=*' } | Select-Object -First 1).Split('=',2)[1]
$Headers = @{ Authorization = "Bearer $GatewayKey" }
Invoke-RestMethod http://127.0.0.1:5000/ready -Headers $Headers
(Invoke-RestMethod http://127.0.0.1:5000/v1/models -Headers $Headers).data.id
```

Expected Z.ai ids include `zai-web` and `zai:glm-5.3` when authenticated discovery succeeds.

## Kilo testing after login

Kilo should use:

```text
Provider: OpenAI-compatible
Base URL: http://127.0.0.1:5000/v1
API key: BRIDGE_API_KEY from .env
```

Use a model only when `/ready` reports the provider as authenticated/ready and `/v1/models` exposes it.

Recommended first Kilo test:

```text
model: chatgpt-web
prompt: Reply exactly: KILO_HWG_OK
```

Then test authenticated provider models:

```text
zai:glm-5.3
qwen:qwen3.8-max
```

Do not test Qwen while it is in guest mode. Do not treat guest quota errors as valid operation.

## Failure handling

### `auth_required`

The provider profile is not logged in or session detection did not confirm authentication. Re-login through the official provider UI.

### Provider CAPTCHA/challenge

Stop automation and complete the provider's official challenge manually in the same dedicated profile. Do not automate CAPTCHA solving.

### Account suspension or risk-control block

Open the circuit breaker for that provider. Do not rotate account/IP, do not bypass, and do not retry until legitimate restoration and human review.

### Model missing from `/v1/models`

The provider catalog was not available from the authenticated session. Verify login state first, then re-check `/ready` and `/v1/models`.

## Evidence to collect without secrets

Allowed:

- provider id;
- model id;
- ready status;
- session mode `authenticated` or `guest`;
- normalized error type;
- model-evidence metadata;
- HTTP status;
- frontend version;
- timestamps.

Forbidden:

- passwords;
- one-time codes;
- bearer tokens;
- cookies;
- localStorage/sessionStorage values;
- authorization headers;
- CAPTCHA proof;
- raw provider request bodies containing credentials or proof.
