# Hooshka Web Gateway - Kilo Test Guide

This guide configures Kilo to test Hooshka Web Gateway as an OpenAI-compatible local provider.

## Current local gateway

```text
Base URL: http://127.0.0.1:5000/v1
Service:  HooshkaWebGateway
Auth:     Kilo auth-store credential for provider `hooshka`, sourced from BRIDGE_API_KEY
```

Do not paste the real gateway key into shared chats, screenshots, issues, shell transcripts, or Git.

## Current validated Kilo paths

```text
kilo run -m hooshka/chatgpt-web "Reply exactly: KILO_HWG_CHATGPT_OK"
# PASS: KILO_HWG_CHATGPT_OK

kilo run --agent summary -m hooshka/zai:glm-5.3 "Reply exactly: KILO_HWG_ZAI_GLM53_OK"
# PASS: KILO_HWG_ZAI_GLM53_OK
```

Use the Kilo `summary` agent for Z.ai text-only validation because Z.ai currently advertises `tools=false`. The default Kilo `code` agent sends tool schemas; the gateway correctly rejects Z.ai for tool-required requests until Z.ai tool protocol has independent E2 evidence.

## Provider settings

Kilo provider id:

```text
hooshka
```

Provider package/schema:

```text
@ai-sdk/openai-compatible
options.baseURL = http://127.0.0.1:5000/v1
```

Credential must live in Kilo's auth store, not in a public config block. `kilo auth list` should show `hooshka` as an API credential without printing the credential value.

## Recommended test order

1. `hooshka/chatgpt-web` with the default `code` agent.
2. `hooshka/zai:glm-5.3` with `--agent summary`.
3. `hooshka/zai-web` with `--agent summary`.
4. `hooshka/qwen:qwen3.8-max` only after Qwen profile authentication is verified.

Current Qwen status:

```text
session_status: guest
http_status: 401
completion: not executed
```

## Interpreting failures

### 401 Unauthorized

The Kilo credential for provider `hooshka` is missing or wrong. Register the local gateway key through Kilo's auth flow; do not write it into tracked project files.

### No provider supports model with requested capabilities

Kilo requested a capability that the target Web provider does not advertise. This is expected for Z.ai/Qwen when the default `code` agent sends tools. Use `--agent summary` for text-only validation, or implement and validate provider tool support before advertising it.

### ChatGPT large prompt failures

Kilo agent requests can exceed 60KB because they include system context and tool manifests. ChatGPT Web uses a backend-intercept transport for large agent payloads: the official frontend still performs prepare/session/proof generation, and the gateway only replaces the final conversation request body. No auth/proof values are read, logged, or stored.

### Qwen guest/auth errors

Guest mode is intentionally blocked. Complete official login in `.runtime\qwen-profile`, then verify `session_status.authenticated=true` before running Qwen through Kilo.

## Evidence to record

Record only non-secret evidence:

```text
Kilo agent:
Kilo model id:
Prompt marker:
Observed response:
Gateway version:
Provider session mode:
Model evidence fields, when available:
```

Never record API keys, cookies, bearer headers, session tokens, signatures, CAPTCHA proof, or full provider request bodies.
