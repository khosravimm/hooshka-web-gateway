# Kilo E2 Evidence - 2026-09-11

## Scope

Evidence for Kilo CLI integration with Hooshka Web Gateway as an OpenAI-compatible provider.

## Environment

```text
Repository: D:\Code\hooshka-web-gateway
Gateway service: HooshkaWebGateway
Gateway API: http://127.0.0.1:5000/v1
Kilo extension/backend: kilo.exe 7.6.2
Kilo provider id: hooshka
```

## Authentication policy

Guest Web-chat provider sessions are not accepted. Provider login must be performed through the official provider frontend in the dedicated project browser profile.

## ChatGPT Web E2

Command shape:

```text
kilo run -m hooshka/chatgpt-web "Reply exactly: KILO_HWG_CHATGPT_OK"
```

Observed result:

```text
> code · chatgpt-web
KILO_HWG_CHATGPT_OK
exit_code: 0
```

Accepted conclusions:

- Kilo can select `chatgpt-web` through provider `hooshka`.
- The request reaches Hooshka Web Gateway and returns through Kilo.
- Large Kilo agent prompts are handled without injecting the entire 60KB+ payload into the ChatGPT composer.
- ChatGPT Web now uses a project-owned Chrome CDP runtime on port `9224` and profile `.runtime\chatgpt-profile`.

## Z.ai GLM-5.3 Kilo E2

Command shape:

```text
kilo run --agent summary -m hooshka/zai:glm-5.3 "Reply exactly: KILO_HWG_ZAI_GLM53_OK"
```

Observed result:

```text
> summary · zai:glm-5.3
KILO_HWG_ZAI_GLM53_OK
exit_code: 0
```

Additional direct model-evidence check:

```text
model: zai:glm-5.3
content: ZAI_MODEL_EVIDENCE_OK
requested_upstream_model: glm-5.3
upstream_model: glm-5.3
backend_request_model: glm-5.3
selected_model_label: GLM-5.3
session_mode: authenticated
```

Accepted conclusions:

- Kilo can select `zai:glm-5.3` through provider `hooshka` when using a text-only agent.
- Z.ai session is authenticated.
- UI label, requested upstream model, backend request model and response model align on `glm-5.3`.
- Z.ai tools remain disabled until independent E2 tool protocol validation exists.

## Qwen status

Current Qwen profile status:

```text
authenticated: false
http_status: 401
mode: guest
```

Qwen completion was not executed. This is the expected fail-closed behavior under the mandatory authenticated-session policy.

## Non-claims

- This is E2 evidence only, not E3 reliability evidence.
- This does not validate Z.ai or Qwen tool calling.
- This does not authorize use of guest sessions.
- No API key, cookie, bearer token, provider token, signature, CAPTCHA proof, or full provider request body was recorded.
