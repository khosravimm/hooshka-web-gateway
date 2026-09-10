# Hooshka Web Gateway — Troubleshooting

This is the current 0.5.1 troubleshooting guide. Older `troubleshooting.md` is historical and may reference pre-migration names or behavior.

## Fast triage

```powershell
cd D:\Code\hooshka-web-gateway
Get-Service HooshkaWebGateway
Get-NetTCPConnection -LocalPort 5000 -State Listen -ErrorAction SilentlyContinue
.\service_manager.ps1 config
.\service_manager.ps1 logs
```

Then query `/health` and `/ready`.

## Service not running

Check:

```powershell
Get-Service HooshkaWebGateway
sc.exe qc HooshkaWebGateway
```

Verify NSSM paths resolve under:

```text
D:\Code\hooshka-web-gateway
```

If paths still reference `mcp-web-bridge`, the service is stale and should be reinstalled through the current service manager.

## Port 5000 not listening

If service says Running but 5000 is absent:

1. read `logs\nssm-error.log`;
2. read `logs\bridge.log`;
3. verify Python venv exists;
4. run deterministic tests;
5. restart once after correcting the cause.

Do not repeatedly restart without diagnosis.

## /health works but /ready is degraded

This means the gateway is alive but one or more provider runtimes are unavailable.

Check the provider named in `/ready`.

## ChatGPT Web

Typical failure classes:

- CDP unavailable;
- expected authenticated/context tab absent;
- UI selector drift;
- response completion detection drift;
- tool syntax ambiguity.

Do not broaden retry behavior after a possible submit.

## Qwen Web

Typical failures:

- frontend module bootstrap drift;
- dedicated profile/browser launch failure;
- controller/state discovery changed;
- first-event or meaningful-idle timeout;
- provider challenge/risk-control.

Inspect logs for controller lifecycle and timeout state. Do not switch to arbitrary DOM automation as a silent fallback.

## Z.ai Web

Verify dedicated CDP:

```powershell
Invoke-RestMethod http://127.0.0.1:9223/json/version
```

Expected runtime profile:

```text
D:\Code\hooshka-web-gateway\.runtime\zai-profile
```

Failure classes include:

- CDP absent/wrong browser;
- frontend module/state drift;
- authentication/session loss;
- CAPTCHA/challenge;
- provider backend timeout.

If CAPTCHA requires interaction, stop automated submission and have the operator complete the provider's normal challenge in that session. Do not solve/bypass it automatically.

## Repeated Z.ai windows

First determine whether there are multiple *root* browser processes or merely Chrome renderer/utility child processes.

Owned root identification requires both:

- `--remote-debugging-port=9223`
- `--user-data-dir=...\.runtime\zai-profile`
- no `--type=...` child-process argument

Only owned profile processes may be stopped.

## DeepSeek

If the account is suspended/muted/challenged:

- mark provider unavailable;
- do not retry;
- do not rotate account/IP;
- do not bypass;
- wait for legitimate restoration and human review.

## 401 from gateway

Check that the caller sends:

```text
Authorization: Bearer <runtime-key>
```

Do not place the key in tracked `config.yaml`.

## 429

Two distinct cases exist:

- local gateway rate limit;
- provider-side rate/risk control.

Do not respond to provider 429 by increasing retries. Reduce traffic and investigate.

## HTTP 200 but no valid completion

Provider Web backends can return HTTP 200 with an application-level error envelope. The upstream classifier should treat these as failures. Inspect normalized error class and content type.

## Streaming appears buffered

Check `provider_meta.streaming_mode`.

- `buffered` means output is delivered after provider completion.
- `reconstructed` means gateway output is reconstructed from provider/browser runtime state.
- Neither should be described as native upstream token streaming.

## Regression diagnosis

```powershell
.\.venv\Scripts\python.exe -m compileall -q .
.\.venv\Scripts\python.exe -m pytest -q
git diff --check
git status --short --branch
```

If deterministic tests fail, fix them before doing more live Web requests.

## When to stop testing

Stop immediately on:

- account suspension/mute;
- repeated CAPTCHA/challenge;
- evidence of duplicate submissions;
- uncontrolled browser spawning;
- secret exposure;
- unexplained provider-side enforcement.

Record the incident before resuming.
