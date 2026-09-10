# Hooshka Web Gateway - Browser Observability Layer

**Baseline:** 0.6.1

## Purpose

Browser-backed Web-chat providers can drift independently across UI, frontend state, backend request payloads and response metadata. A request must not be declared successful merely because the UI accepted a prompt.

Hooshka Web Gateway therefore maintains a model-evidence chain:

```text
requested gateway model
        |
        v
expected upstream model
        |
        +--> UI selected model
        +--> frontend runtime state
        +--> observed backend request model
        +--> response model
```

A successful completion is accepted only when the required evidence channels agree.

## Shared implementation

Core module:

```text
core/browser_observability.py
```

Main types:

- `BrowserModelEvidence`
- `BrowserEvidenceMismatch`
- `normalize_model_marker()`

The normalizer allows harmless display/id formatting differences such as:

```text
GLM-5.3      == glm-5.3
Qwen3.8-Max  == qwen3.8-max
```

It does not allow semantic model substitution such as:

```text
GLM-5.3 != GLM-5.3-Flash
glm-5.3 != x-preview-l
```

## Fail-closed rules

For browser-controller providers, successful completion requires:

1. an expected upstream model;
2. UI/frontend selection evidence;
3. an observed backend request model;
4. backend request model equal to the expected model;
5. response model, when available, equal to the expected model.

A mismatch raises normalized provider error type:

```text
model_evidence_mismatch
```

No response is marked successful when the evidence chain contradicts the requested/default model.

## Z.ai

Observed channels:

- requested/default upstream model;
- visible model-selector label;
- actual backend completion request model;
- frontend assistant model;
- backend response HTTP status/content-type;
- bounded backend lifecycle metadata.

The Z.ai transport tolerates navigation races by retrying **observation only** after execution-context replacement. The submit action is not replayed.

Current verified GLM-5.3 evidence from the previous accepted window:

```text
requested gateway model: zai-web
expected upstream model: glm-5.3
UI selected model: GLM-5.3
backend request model: glm-5.3
response model: glm-5.3
response text: ZAI_DEFAULT_MODEL_OK
```

After adding the stricter shared observability layer, one additional Z.ai live check exposed a navigation/context-replacement race. That check is not counted as a successful E2 acceptance. The deterministic E1 layer remains accepted and Z.ai GLM-5.3 default routing remains accepted from the prior evidence window.

## Qwen

Observed channels:

- requested/default upstream model;
- frontend feature-manager selected model ids;
- actual backend request model;
- response model when available;
- safe request/response lifecycle metadata.

The current guest session reached the provider's daily guest quota during verification. Routing/model selection was observed as `qwen3.8-max`, but completion availability is currently blocked by provider `RateLimited` state. The gateway reports this as `rate_limit`, not as an empty successful completion.

## Safe metadata policy

Browser observability may record:

- provider/model ids;
- frontend version;
- UI model label;
- backend request model;
- response model;
- endpoint path without query parameters;
- HTTP status;
- content type;
- lifecycle event type.

It must not record:

- bearer tokens;
- cookies;
- browser storage secrets;
- signatures;
- CAPTCHA proof;
- authorization headers;
- raw provider request bodies;
- raw prompts merely for observability;
- private reasoning content.

## Runtime drift detection

A future provider/frontend change should be treated as drift when any of these occur:

- model selector cannot be resolved;
- frontend state no longer exposes selected model;
- completion endpoint changes unexpectedly;
- backend model differs from selected/requested model;
- response model differs from backend request model;
- expected runtime store disappears;
- repeated navigation/context replacement exceeds bounded observation retries.

Drift should fail closed and trigger provider-specific revalidation rather than silent DOM guessing.

## Controlled DOM policy

DOM interaction is allowed for provider-local control and verification when it is the strongest available evidence, for example model selection.

DOM interaction is not a license to bypass provider controls. CAPTCHA/WAF/account restrictions remain terminal or human-interaction conditions.

## Evidence level

The Browser Observability layer has deterministic E1 coverage in the current code. Z.ai GLM-5.3 default routing has prior E2 evidence. The stricter browser-observability E2 check exposed a navigation race and is recorded as follow-up work, not as a pass.

No E3 reliability claim is made.
