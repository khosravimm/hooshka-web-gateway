# Hooshka Web Gateway — User Test Guide

**Purpose:** quick local acceptance tests for the operator.

## 1. Service check

```powershell
cd D:\Code\hooshka-web-gateway
.\service_manager.ps1 status
Invoke-RestMethod http://127.0.0.1:5000/health
```

Expected service:

```text
HooshkaWebGateway: Running
```

## 2. Load the gateway key safely

Do not print or share the key.

```powershell
$GatewayKey = (Get-Content .\.env | Where-Object { $_ -match '^BRIDGE_API_KEY=' } | Select-Object -First 1) -replace '^BRIDGE_API_KEY=', ''
$Headers = @{ Authorization = "Bearer $GatewayKey"; 'Content-Type' = 'application/json' }
```

## 3. Read readiness and models

```powershell
Invoke-RestMethod http://127.0.0.1:5000/ready -Headers $Headers
(Invoke-RestMethod http://127.0.0.1:5000/v1/models -Headers $Headers).data.id
```

You should see canonical and namespaced models, including:

```text
zai-web
zai:glm-5.3
qwen-web
qwen:qwen3.8-max
```

## 4. Test Z.ai default model

`zai-web` is configured to use `glm-5.3` by default.

GLM-5.3 / Think Max can take noticeably longer than Flash models. The client timeout below is intentionally long.

```powershell
$Body = @{
  model = 'zai-web'
  messages = @(@{ role = 'user'; content = 'Reply exactly: USER_ZAI_GLM53_OK' })
  stream = $false
} | ConvertTo-Json -Depth 8

$Response = Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:5000/v1/chat/completions `
  -Headers $Headers `
  -ContentType 'application/json' `
  -Body $Body `
  -TimeoutSec 480

$Response.choices[0].message.content
$Response.provider_meta | ConvertTo-Json -Depth 10
```

Acceptance criteria:

```text
content == USER_ZAI_GLM53_OK
provider_meta.requested_upstream_model == glm-5.3
provider_meta.selected_model_label == GLM-5.3
provider_meta.backend_request_model == glm-5.3
provider_meta.upstream_model == glm-5.3
provider_meta.model_evidence.verified == true
```

If the response is delayed but Z.ai UI shows Think/Reasoning progress, wait. Do not retry immediately.

## 5. Test explicit Z.ai model

```powershell
$Body = @{
  model = 'zai:glm-5.3'
  messages = @(@{ role = 'user'; content = 'Reply exactly: USER_ZAI_EXPLICIT_GLM53_OK' })
  stream = $false
} | ConvertTo-Json -Depth 8

$Response = Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:5000/v1/chat/completions `
  -Headers $Headers `
  -ContentType 'application/json' `
  -Body $Body `
  -TimeoutSec 480

$Response.choices[0].message.content
$Response.provider_meta | ConvertTo-Json -Depth 10
```

## 6. Test Qwen default model

`qwen-web` is configured to use `qwen3.8-max` by default.

Current known limitation: the current Qwen guest session has reached its daily provider quota. If quota remains active, this test should return a normalized rate-limit error rather than an empty success.

```powershell
$Body = @{
  model = 'qwen-web'
  messages = @(@{ role = 'user'; content = 'Reply exactly: USER_QWEN_MAX_OK' })
  stream = $false
} | ConvertTo-Json -Depth 8

Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:5000/v1/chat/completions `
  -Headers $Headers `
  -ContentType 'application/json' `
  -Body $Body `
  -TimeoutSec 240
```

Acceptance after quota resets:

```text
content == USER_QWEN_MAX_OK
provider_meta.upstream_model == qwen3.8-max
provider_meta.backend_request_model == qwen3.8-max
provider_meta.model_evidence.verified == true
```

## 7. Important safety rules

- Do not run repeated live tests in a loop.
- Do not retry immediately if Think Max is still reasoning.
- Do not bypass CAPTCHA/WAF/account restrictions.
- Do not paste `.env`, bearer keys, cookies, tokens or browser storage into chat/logs.
- If a provider returns rate limit or account restriction, stop testing that provider.
