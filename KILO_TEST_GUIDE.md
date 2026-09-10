# Hooshka Web Gateway - Kilo Test Guide

This guide configures Kilo to test Hooshka Web Gateway as an OpenAI-compatible local provider.

## Current local gateway

```text
Base URL: http://127.0.0.1:5000/v1
Service:  HooshkaWebGateway
Auth:     Bearer token from .env / BRIDGE_API_KEY
```

Do not paste the real gateway key into shared chats, screenshots, issues, or Git.

## Recommended first test model

Use this first because it is the most likely to validate Kilo compatibility quickly:

```text
chatgpt-web
```

Then test:

```text
qwen:qwen3.8-max
qwen-web
zai:glm-5.3
zai-web
```

Notes:

- `qwen-web` defaults to `qwen3.8-max`, but the current Qwen guest session may be daily-quota limited.
- `zai-web` defaults to `glm-5.3`, which can be slow in Think Max mode. Use a long timeout and do not retry quickly.
- If Z.ai is still thinking, wait. Fast retries can create several half-finished conversations.

## Kilo provider settings

In Kilo, create or edit an OpenAI-compatible provider:

```text
Provider type: OpenAI Compatible / OpenAI API-compatible
Base URL:      http://127.0.0.1:5000/v1
API key:       value of BRIDGE_API_KEY from D:\Code\hooshka-web-gateway\.env
Model:         chatgpt-web
```

If Kilo has separate fields:

```text
Host:     http://127.0.0.1:5000
Base API: /v1
Models:   use manual/custom model id
```

## Get the gateway key locally without printing it

PowerShell:

```powershell
cd D:\Code\hooshka-web-gateway
$GatewayKey = (Get-Content .\.env | Where-Object { $_ -match '^BRIDGE_API_KEY=' } | Select-Object -First 1) -replace '^BRIDGE_API_KEY=', ''
```

Then paste the value into Kilo's API key field only if you are working locally and not sharing the screen/log.

## Pre-check from PowerShell

```powershell
cd D:\Code\hooshka-web-gateway
.\service_manager.ps1 status
Invoke-RestMethod http://127.0.0.1:5000/health
```

Authenticated model list:

```powershell
$GatewayKey = (Get-Content .\.env | Where-Object { $_ -match '^BRIDGE_API_KEY=' } | Select-Object -First 1) -replace '^BRIDGE_API_KEY=', ''
$Headers = @{ Authorization = "Bearer $GatewayKey" }
(Invoke-RestMethod http://127.0.0.1:5000/v1/models -Headers $Headers).data.id
```

## Minimal Kilo prompt

Use this prompt for the first Kilo smoke test:

```text
Reply exactly: KILO_HWG_OK
```

Expected successful result:

```text
KILO_HWG_OK
```

## Test sequence

1. Start with `chatgpt-web`.
2. If Kilo can call the gateway and return `KILO_HWG_OK`, provider compatibility is OK.
3. Switch model to `zai:glm-5.3` or `zai-web` and use a longer wait because Think Max is slow.
4. Switch model to `qwen:qwen3.8-max` only after Qwen guest quota is available or you have a logged-in Qwen session.

## Interpreting failures

### 401 Unauthorized

The API key in Kilo is missing or wrong. Use the value of `BRIDGE_API_KEY` from `.env`.

### Model not found

Kilo may be using a model id not returned by `/v1/models`. Re-check the current model list.

### Timeout on Z.ai

GLM-5.3 / Think Max can take several minutes. Do not retry immediately. Check the Z.ai browser window and wait if it is still thinking.

### Qwen rate limit

The current guest session has shown daily quota exhaustion. This is a provider quota state, not necessarily a gateway/Kilo configuration error.

### Empty answer

Empty answers should be treated as failure. The gateway has fail-closed checks for known Qwen empty-response/rate-limit cases.

## Evidence to record after test

Record only non-secret evidence:

```text
Kilo provider type:
Base URL:
Model id:
Prompt:
Observed response:
HTTP/status/error shown by Kilo:
Gateway version:
Provider metadata if visible:
```

Never record API keys, cookies, bearer headers, session tokens, signatures, or CAPTCHA proof.
