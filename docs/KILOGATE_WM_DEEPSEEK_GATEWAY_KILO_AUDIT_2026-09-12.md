# KiloGate-WM DeepSeek Gateway/Kilo Audit - 2026-09-12

## Scope

This audit records the controlled implementation and certification evidence for `deepseek-web` as a Hooshka Web Gateway browser-UI provider and as a Kilo tool-capable model.

The audited path is:

```text
Kilo CLI
  -> OpenAI-compatible Hooshka Web Gateway
  -> deepseek-web provider
  -> project-owned DeepSeek Chrome CDP runtime
  -> DeepSeek Web Chat UI
```

No DeepSeek API token, backend signature bypass, CAPTCHA bypass, WAF bypass, or silent cross-provider fallback is part of this certification.

## Runtime boundary

```text
DeepSeek CDP: 127.0.0.1:9226
Profile: .runtime/deepseek-profile
Transport: browser_ui
Model id: deepseek-web
Kilo dev provider during audit: hooshka-dev/deepseek-web
```

The DeepSeek browser profile was authenticated during testing and exposed a usable chat textarea. The runtime is a project-owned Chrome profile separate from the ChatGPT, Qwen and Z.ai profiles.

## Deterministic gates

The deterministic/provider tests added for this work cover:

- provider metadata and `supports_model` routing;
- text-only completion normalization;
- required tool-call envelope parsing;
- tool-result continuation to final answer;
- fail-closed required tool protocol behavior;
- provider UI block detection boundaries;
- post-tool final answer acceptance;
- tolerant parsing for raw Windows paths emitted by Web-chat models.

Current targeted result before final merge gate:

```text
tests/test_deepseek_web_provider.py + tests/test_tool_protocol.py: 15 passed
```

## Provider-level E2 evidence

Evidence file:

```text
.runtime/kilogate_deepseek_web_provider_e2_20260912.json
```

Result:

| Case | Expected | Result |
|---|---|---:|
| direct marker | exact assistant final text | PASS |
| required read_file tool call | machine-parseable tool call | PASS |
| tool-result continuation | exact assistant final text | PASS |

Summary:

```text
3 rows, 3 PASS, 0 FAIL
```

## Gateway API E2 evidence

Evidence file:

```text
.runtime/kilogate_deepseek_gateway_api_e2_20260912.json
```

Test endpoint:

```text
http://127.0.0.1:5002/v1/chat/completions
```

Result:

| Case | HTTP | Expected | Result |
|---|---:|---|---:|
| direct marker | 200 | exact assistant final text | PASS |
| required read_file tool call | 200 | `finish_reason=tool_calls` | PASS |
| tool-result continuation | 200 | exact assistant final text | PASS |

Summary:

```text
3 rows, 3 PASS, 0 FAIL
```

## Kilo CLI tool evidence

Kilo was configured with a temporary audit provider:

```text
hooshka-dev/deepseek-web -> http://127.0.0.1:5002/v1
```

The following Kilo controls passed:

| Control | Tool(s) observed | Result |
|---|---|---:|
| text-only smoke | none | PASS |
| read file | `read` | PASS |
| project search | `grep` | PASS |
| create probe file | `write` | PASS |
| edit probe file | `edit` | PASS |
| shell verification | `bash` | PASS |

Observed markers:

```text
KGWM_KILO_DEEPSEEK_TEXT_OK_20260912C
KGWM_KILO_DEEPSEEK_READFILE_OK_20260912C
KGWM_KILO_DEEPSEEK_SEARCH_OK_20260912
KGWM_KILO_DEEPSEEK_SHELL_OK_20260912
```

The write/edit/shell probe used only a temporary runtime file:

```text
.runtime/kilogate_deepseek_patch_probe.txt
```

Final probe content:

```text
KGWM_PATCH_AFTER_20260912
```

## Fixes discovered during the audit

### CDP runtime isolation

An early test incorrectly targeted the Z.ai runtime on port `9223`. DeepSeek now uses a dedicated runtime on `9226` and service-manager support was added for that profile.

### UI-state detection false positives

The first Kilo text smoke returned the correct marker in DeepSeek, but the provider rejected it because the detector read Kilo's large prompt text and falsely interpreted words such as login-related terms as a UI login state. Detection was narrowed to account/page state and treats an active textarea as authenticated unless explicit blocking signals are present.

### Windows-path JSON repair

DeepSeek emitted valid-intent tool envelopes containing Windows paths with raw backslashes. A bounded tolerant JSON loader now repairs only invalid backslashes that break machine parsing, allowing Kilo file-tool calls to proceed without accepting arbitrary prose.

### Post-tool final handling

After Kilo returned a tool result, the provider initially rejected a correct final answer because the original user prompt still mentioned tool use. The provider now allows a final answer after a `role=tool` message when no additional tool call is needed.

## Certification statement

`deepseek-web` is accepted as **KiloGate-WM E2 tool-capable smoke certified** for the following tool classes:

```text
read, grep, write, edit, bash
```

This is not an E3/production reliability claim. It does not authorize high-volume tests, stress tests, organizational/SUMS sensitive data, CAPTCHA/WAF bypass, or silent fallback to another provider.

## Remaining constraints

- The transport depends on the authenticated project-owned DeepSeek browser profile.
- Web Chat UI changes can break selectors and require re-certification.
- DeepSeek frequently emits JSON-like tool envelopes that require bounded repair for Windows paths; parser changes must remain fail-closed.
- Full production certification requires longer stability/recovery testing beyond this E2 smoke audit.
