# Hooshka Web Gateway — Practical Usage Guide

**Release baseline:** 0.5.1

This guide covers day-to-day use from PowerShell, Python, scripts and Hooshka-compatible clients.

## 1. Verify the service

```powershell
cd D:\Code\hooshka-web-gateway
.\service_manager.ps1 status
```

Expected service: `HooshkaWebGateway`.

If stopped:

```powershell
.\service_manager.ps1 start
```

## 2. Check health and readiness

```powershell
Invoke-RestMethod http://127.0.0.1:5000/health
$GatewayKey = (Get-Content .\.env | Where-Object { $_ -like 'BRIDGE_API_KEY=*' } | Select-Object -First 1).Split('=',2)[1]
$Headers = @{ Authorization = "Bearer $GatewayKey" }
Invoke-RestMethod http://127.0.0.1:5000/ready -Headers $Headers
```

Do not echo `$GatewayKey` or paste it into shared logs.

## 3. List providers and models

```powershell
Invoke-RestMethod http://127.0.0.1:5000/modes -Headers $Headers
Invoke-RestMethod http://127.0.0.1:5000/v1/models -Headers $Headers
```

Current canonical models are `chatgpt-web`, `qwen-web`, and `zai-web`.

## 4. Send a basic request from PowerShell

```powershell
$Body = @{ model='qwen-web'; messages=@(@{role='user';content='Explain DNSSEC in three points.'}); stream=$false } | ConvertTo-Json -Depth 8
$Response = Invoke-RestMethod -Method Post -Uri http://127.0.0.1:5000/v1/chat/completions -Headers $Headers -ContentType 'application/json' -Body $Body
$Response.choices[0].message.content
```

Change only the canonical model id to select another provider explicitly.

## 5. Python requests

```python
import os
import requests

response = requests.post(
    'http://127.0.0.1:5000/v1/chat/completions',
    headers={'Authorization': 'Bearer ' + os.environ['HOOSHKA_WEB_GATEWAY_KEY']},
    json={
        'model': 'zai-web',
        'messages': [{'role': 'user', 'content': 'Explain certificate pinning briefly.'}],
        'stream': False,
    },
    timeout=180,
)
response.raise_for_status()
print(response.json()['choices'][0]['message']['content'])
```

Prefer process environment injection for the key instead of embedding it in source.

## 6. OpenAI-compatible Python client

```python
from openai import OpenAI
import os

client = OpenAI(
    api_key=os.environ['HOOSHKA_WEB_GATEWAY_KEY'],
    base_url='http://127.0.0.1:5000/v1',
)

response = client.chat.completions.create(
    model='chatgpt-web',
    messages=[{'role': 'user', 'content': 'Explain HSTS briefly.'}],
)
print(response.choices[0].message.content)
```

Compatibility depends on the client using standard Chat Completions semantics.

## 7. Streaming

Set `stream: true`. The gateway emits OpenAI-style SSE data frames and terminates with `data: [DONE]`.

Streaming provenance is provider-specific. `buffered` and `reconstructed` are not claims of native upstream token streaming.

## 8. Thinking option

Qwen has an E2-tested thinking-mode mapping. Example:

```json
{
  "model": "qwen-web",
  "messages": [{"role": "user", "content": "Analyze this design."}],
  "thinking": false
}
```

Do not assume identical thinking semantics across providers.

## 9. Tool calling

Only send tools when `/modes` reports `tools=true` for the selected provider. ChatGPT Web currently has an E2-tested tool path. Qwen and Z.ai tools remain disabled.

## 10. Safe provider selection

Good: explicit `model: zai-web`.

Do not request "any available AI" and do not build silent cross-provider fallback. The caller must make any cross-provider policy decision before submission.

## 11. Common operational scenarios

- Gateway alive but provider not ready: inspect `/ready` and provider troubleshooting; do not loop restarts.
- CAPTCHA appears: use the provider's normal human challenge flow; do not automate bypass.
- DeepSeek blocked: do not retry or rotate account/IP.
- Unexpected Z.ai windows: use owned-profile checks in `OPERATIONS_RUNBOOK.md`; never close ordinary Chrome tabs by URL alone.

## 12. Safe Hooshka flow

```text
Hooshka job
  -> data classification / policy gate
  -> /ready
  -> /modes
  -> explicit provider/model selection
  -> /v1/chat/completions
  -> normalized result + provider_meta
```

## 13. Before reporting a bug

Collect only non-secret evidence: release/version, provider/model, endpoint, HTTP status, normalized error type, sanitized `provider_meta`, timestamps and service/readiness state.

Never include bearer keys, cookies, authorization headers, CAPTCHA proof values or browser-storage tokens.
