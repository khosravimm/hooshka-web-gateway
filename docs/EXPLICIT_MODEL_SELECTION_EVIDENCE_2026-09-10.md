# Explicit Model Selection Evidence — 2026-09-10

## Scope

This record covers explicit upstream model selection for:

- Z.ai: `GLM-5.3` — upstream id `glm-5.3`
- Qwen: `Qwen3.8-Max` — upstream id `qwen3.8-max`

The objective is to prove that the gateway is not merely calling the provider default model behind a generic alias.

## Rejected Z.ai test

An earlier Z.ai completion returned successfully while the visible selector was **GLM-5.3-Flash** and response metadata reported `x-preview-l`.

That test is **REJECTED as evidence for GLM-5.3**.

It proves only that Z.ai completion worked with the Flash/default model. It must not be cited as GLM-5.3 acceptance evidence.

## Z.ai strict acceptance criteria

A Z.ai GLM-5.3 test is accepted only when all of these agree:

1. canonical request model: `zai:glm-5.3`;
2. visible provider selector after the transport reload: `GLM-5.3`;
3. actual backend completion request body: `model=glm-5.3`;
4. observed upstream/assistant model metadata: `glm-5.3`;
5. completion returns successfully.

### Accepted E2 evidence

Observed result:

```text
response_model=zai:glm-5.3
selected_model_label=GLM-5.3
backend_request_model=glm-5.3
upstream_model=glm-5.3
session_mode=authenticated
completion=PASS
```

Disposition: **E2 explicit-model routing PASS for Z.ai GLM-5.3.**

## Qwen strict acceptance criteria

Qwen explicit model selection uses the provider frontend feature manager method:

```text
setSingleModel("qwen3.8-max")
```

Acceptance requires:

1. canonical request model: `qwen:qwen3.8-max`;
2. frontend selected model contains id `qwen3.8-max`;
3. actual backend completion request body reports `qwen3.8-max`;
4. gateway upstream model metadata reports `qwen3.8-max`;
5. completion returns without a provider/model-selection error.

### Accepted E2 routing evidence

Observed result:

```text
response_model=qwen:qwen3.8-max
selected_model_id=qwen3.8-max
backend_request_model=qwen3.8-max
upstream_model=qwen3.8-max
session_mode=guest
frontend_version=0.2.91
completion=returned
```

The model did not follow the exact-string wording of the smoke prompt, so that individual content assertion was false. This does **not** invalidate the routing evidence because frontend selection and the real backend request both independently prove `qwen3.8-max`.

Disposition: **E2 explicit-model routing PASS for Qwen3.8-Max. Exact-text compliance is not claimed by this evidence.**

## Security of evidence collection

Only model identifiers and safe runtime metadata are retained.

The implementation does not intentionally expose or retain:

- bearer tokens;
- cookies;
- authorization headers;
- CAPTCHA proof;
- signatures;
- browser storage credentials.

## Canonical model ids

Clients should use:

```text
zai:glm-5.3
qwen:qwen3.8-max
```

Generic compatibility aliases remain:

```text
zai-web
qwen-web
```

In 0.6.0 these generic aliases use a configurable provider default. Current tracked defaults are:

```text
qwen-web -> qwen3.8-max
zai-web  -> glm-5.3
```

Explicit namespaced ids remain available for exact model selection.

## 2026-09-10 late-window verification — dynamic catalog and defaults

Deterministic gate after the catalog/default-policy changes:

```text
pytest: 58 passed
git diff --check: PASS
service: HooshkaWebGateway Running
```

Live `/v1/models` discovery returned **20 routable ids** in the current session:

- Z.ai: 16 entries (`zai-web` plus 15 discovered upstream ids);
- Qwen: 3 entries (`qwen-web`, `qwen:qwen3.7-plus`, `qwen:qwen3.8-max`);
- ChatGPT Web: 1 entry.

This verifies that the public model list is not restricted to only manually named aliases. New upstream models can be surfaced through provider catalog discovery and namespaced routing, subject to the active session's advertised catalog.

### Z.ai default-model E2

One controlled request using the generic model `zai-web` completed successfully with all model-selection evidence aligned:

```text
response_model=zai-web
requested_upstream_model=glm-5.3
selected_model_label=GLM-5.3
backend_request_model=glm-5.3
upstream_model=glm-5.3
session_mode=authenticated
content=ZAI_DEFAULT_MODEL_OK
```

Disposition: **E2 PASS for configurable default routing `zai-web -> glm-5.3`.**

During this verification a Z.ai first-event timeout was traced to provider navigation replacing the page execution context after submit. The transport now re-bootstraps the provider runtime stores after navigation before continuing response polling.

### Qwen default-model routing and current quota state

Controlled requests using both `qwen-web` and explicit Qwen ids showed the actual backend request and frontend selection using the requested upstream model. For the generic alias:

```text
requested model=qwen-web
selected_model_id=qwen3.8-max
backend_request_model=qwen3.8-max
session_mode=guest
```

The current guest session then returned provider error code `RateLimited` with the message that the daily guest chat limit had been reached. No additional Qwen live completion tests should be repeated in this quota window.

Disposition:

- **default routing evidence PASS** for `qwen-web -> qwen3.8-max`;
- **completion availability BLOCKED by current guest quota**, not by routing/model selection;
- the gateway now classifies this provider response as `rate_limit` instead of accepting an empty completion.

## Evidence integrity correction

`backend_request_model` is now populated only from an observed provider backend request in browser-controller transports. The requested/default model is kept separately and is not substituted as backend evidence when no backend request was observed.

## Browser Observability verification — 0.6.2 patch window

A controlled Z.ai request was executed after the shared Browser Observability layer and navigation-race handling were active.

Observed chain:

```text
gateway_model=zai-web
expected_upstream_model=glm-5.3
ui_selected_model=GLM-5.3
backend_request_model=glm-5.3
response_model=glm-5.3
content=ZAI_BROWSER_OBS_OK
model_evidence.verified=true
selection_verified=true
backend_verified=true
response_verified=true
```

Disposition: **E2 PASS for the full Z.ai model-evidence chain.**

The transport also records safe backend lifecycle metadata (request/response event type, model id, HTTP status and content type only). It does not record provider credentials, cookies, signatures, CAPTCHA proof or raw request bodies.

Qwen was intentionally not re-run for completion in this patch window because the current guest session had already returned provider `RateLimited` for the daily guest quota. Existing routing evidence remains valid; completion availability remains quota-blocked for that session.
