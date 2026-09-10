# Hooshka Web Gateway — Canonical Identity and Migration Plan

## Decision

The unified Web-chat integration project is named **Hooshka Web Gateway**.

Canonical identifiers:

- Product name: `Hooshka Web Gateway`
- Repository: `khosravimm/hooshka-web-gateway`
- Local path: `D:\Code\hooshka-web-gateway`
- Hooshka module id: `web_gateway`
- Python namespace target: `hooshka_web_gateway`
- Windows service: `HooshkaWebGateway`
- API identity: `hooshka-web-gateway`
- Legacy repository id: `mcp-web-bridge`
- Legacy Windows service: `WebLLMBridge`

## Mission boundary

Hooshka Web Gateway is the single governed adapter/gateway for Web-chat providers. It owns OpenAI-compatible gateway endpoints, provider routing, Web-chat transports, browser/CDP runtime ownership, Web-session/account-state controls, stream normalization, capability declarations and provider-specific evidence.

Hooshka orchestration, RAG/knowledge-bank logic and unrelated browser automation remain outside this module.

## Provider ids

- `chatgpt-web`
- `qwen-web`
- `zai-web`
- `deepseek-web`

## Migration status

### Phase A — canonical identity: COMPLETE

Documentation, API metadata and control-panel branding use Hooshka Web Gateway.

### Phase B — runtime/repository rename: COMPLETE

- local repository path: `D:\Code\hooshka-web-gateway`;
- GitHub repository: `khosravimm/hooshka-web-gateway`;
- Windows service: `HooshkaWebGateway`;
- legacy `WebLLMBridge` service removed;
- rollback ref: `rollback/pre-hooshka-web-gateway-migration`.

### Phase C — Hooshka integration: READY FOR INTEGRATION

Hooshka should consume module `web_gateway` through the local API contract rather than provider internals.

## Migration gate result

- deterministic suite: PASS, 54/54;
- `git diff --check`: PASS before final documentation commit;
- secret scan: PASS before migration;
- canonical service installation/start: PASS;
- localhost listeners: PASS;
- `/health`: PASS;
- `/ready`: PASS;
- `/modes`: PASS;
- `/v1/models`: PASS;
- post-migration ChatGPT Web smoke: PASS;
- post-migration Qwen Web smoke: PASS;
- post-migration Z.ai Web smoke: PASS.

## Naming rule

New product-level work must use **Hooshka Web Gateway**. Legacy names may appear only in compatibility, historical evidence or migration cleanup.
