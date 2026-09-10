# Hooshka Web Gateway — Operations Runbook

## Service identity

- Windows service: `HooshkaWebGateway`
- Local path: `D:\Code\hooshka-web-gateway`
- HTTP listener: `127.0.0.1:5000`
- Z.ai owned CDP: `127.0.0.1:9223`

## Normal operations

### Status

```powershell
cd D:\Code\hooshka-web-gateway
.\service_manager.ps1 status
```

### Start

```powershell
.\service_manager.ps1 start
```

### Stop

```powershell
.\service_manager.ps1 stop
```

Stopping performs cleanup only for browser runtimes identified as gateway-owned by their profile paths.

### Restart

```powershell
.\service_manager.ps1 restart
```

Do not loop restart commands. If restart fails twice, diagnose instead of retrying indefinitely.

### Effective service configuration

```powershell
.\service_manager.ps1 config
```

### Logs

```powershell
.\service_manager.ps1 logs
Get-Content .\logs\audit.log -Tail 80
```

## Health sequence

Use this order:

1. Windows service status.
2. Listener on 5000.
3. `GET /health`.
4. `GET /ready`.
5. `GET /modes`.
6. `GET /v1/models`.
7. Only if needed, one low-risk provider smoke.

A green `/health` with red provider readiness means the HTTP gateway is alive but a provider runtime/session is not ready.

## Windows checks

```powershell
Get-Service HooshkaWebGateway
Get-NetTCPConnection -LocalPort 5000 -State Listen
Get-NetTCPConnection -LocalPort 9223 -State Listen -ErrorAction SilentlyContinue
```

Expected API bind is loopback only.

## Z.ai browser ownership

There should normally be one root Chrome process for the dedicated Z.ai profile, plus its normal renderer/utility child processes. Multiple Chrome child processes are not multiple browser windows.

Ownership is determined by command line profile:

```text
D:\Code\hooshka-web-gateway\.runtime\zai-profile
```

Do not kill arbitrary `chat.z.ai` tabs in the user's normal Chrome profile.

## Qwen runtime

Qwen uses its dedicated runtime/profile:

```text
.runtime\qwen-profile
```

The service manager cleans gateway-owned Qwen browsers by profile path.

## Safe acceptance after maintenance

Deterministic gate:

```powershell
.\.venv\Scripts\python.exe -m compileall -q .
.\.venv\Scripts\python.exe -m pytest -q
git diff --check
```

Then service/HTTP checks. Use live provider completion tests only when the change touches provider runtime/transport behavior.

## Provider risk budget

Live Web accounts are not load-test infrastructure.

Operational policy:

- concurrency 1 by default;
- no rapid burst testing;
- bounded predefined smoke set;
- no infinite retries;
- stop on CAPTCHA/challenge/suspension/mute;
- no provider account/IP rotation to continue a blocked test;
- no replay after ambiguous submission.

## Incident handling

### Provider challenge/CAPTCHA

Stop automated submission. Allow the provider's normal browser flow. If human interaction is required, ask the operator to solve the challenge in the existing provider-owned session. Resume only after the challenge is legitimately cleared.

### Account suspension/mute

Open circuit breaker for that provider. Do not retry. Record provider state and timestamp. Human review is required before re-enable.

### Repeated unexpected browser windows

1. Stop creating new tests.
2. Check service state.
3. enumerate Chrome command lines for gateway-owned profile paths;
4. stop only owned runtimes;
5. inspect lifecycle/restart logs before restarting.

### HTTP 200 but invalid provider payload

Treat application-level error envelopes as failures. Do not interpret HTTP 200 alone as successful completion.

## Backup/rollback

Pre-migration rollback ref:

```text
rollback/pre-hooshka-web-gateway-migration
```

Before risky release work, create a new rollback tag/ref at the exact accepted SHA.

Never tag/publish from a dirty worktree.
