# Hooshka Web Gateway ? Canonical Identity and Migration Plan

## Decision

The unified Web-chat integration project is henceforth named **Hooshka Web Gateway**.

Canonical identifiers:

- Product name: `Hooshka Web Gateway`
- Repository target name: `hooshka-web-gateway`
- Hooshka module id: `web_gateway`
- Python namespace target: `hooshka_web_gateway`
- Windows service target: `HooshkaWebGateway`
- API identity: `hooshka-web-gateway`
- Legacy project/repository id: `mcp-web-bridge`
- Legacy Windows service name: `WebLLMBridge`

## Mission boundary

Hooshka Web Gateway is the single governed adapter/gateway for Web-chat providers. It owns:

- OpenAI-compatible gateway endpoints;
- provider registry and exact/fail-closed routing;
- provider transports for ChatGPT Web, Qwen Web, Z.ai Web, DeepSeek Web and future Web-chat providers;
- browser/CDP runtime ownership and lifecycle;
- Web-session/captcha/account-state controls;
- SSE normalization and provider capability declarations;
- Web-chat-specific test evidence, rate budgets and operational circuit breakers.

It does **not** own Hooshka orchestration, project management, RAG/knowledge-bank logic or unrelated browser automation. Those remain separate Hooshka modules.

## Provider ids

Provider ids remain stable and are not prefixed with Hooshka:

- `chatgpt-web`
- `qwen-web`
- `zai-web`
- `deepseek-web`

This keeps client routing compact while the gateway itself supplies the Hooshka module boundary.

## Migration policy

Migration is deliberately non-breaking.

### Phase A ? canonical identity (current)

- Public documentation, API metadata and control-panel branding use `Hooshka Web Gateway`.
- `mcp-web-bridge` is marked legacy compatibility identity.
- Existing filesystem path and Windows service remain unchanged while regression/E2 evidence is collected.

### Phase B ? runtime rename

After a clean migration gate:

- repository/folder target becomes `D:\\Code\\hooshka-web-gateway`;
- Windows service target becomes `HooshkaWebGateway`;
- compatibility scripts may recognize `WebLLMBridge` temporarily for upgrade/uninstall;
- no provider profile is migrated by URL matching; only explicit owned profile paths are moved/reused.

### Phase C ? Hooshka integration

Hooshka imports/launches this project as module `web_gateway` through a stable local API boundary rather than importing provider internals. The module exposes health, readiness, provider capabilities, models and chat/stream endpoints.

## Migration gate

Physical repo/service rename is allowed only when all are true:

1. deterministic suite PASS;
2. `git diff --check` PASS;
3. secret scan PASS;
4. service restart PASS;
5. `/health`, `/ready`, `/modes`, `/v1/models` PASS;
6. existing operational provider smoke tests remain PASS;
7. rollback reference is recorded before renaming the filesystem/service;
8. no ordinary user Chrome profile/window will be renamed, moved or stopped.

## Naming rule going forward

Do not introduce new product-level names such as `Web LLM Bridge`, `MCP Web Bridge`, `Universal Web API`, or provider-specific gateway names. They may appear only in historical/evidence context. New product documentation must use **Hooshka Web Gateway**.
