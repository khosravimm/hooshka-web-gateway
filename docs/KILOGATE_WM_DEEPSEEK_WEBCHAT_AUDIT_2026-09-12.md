# KiloGate-WM DeepSeek Web Chat Audit - 2026-09-12

## Scope

This audit corrects the earlier DeepSeek check that exercised the local `deepseek-api-kit-poc` token/backend path. The user requirement is Web Chat operation through `https://chat.deepseek.com/`, not the official API and not a copied local API token.

Target route: real DeepSeek Web Chat UI in the controlled browser session.

Gateway status at the time of this audit:

- `deepseek-web` is not registered/enabled in Hooshka Web Gateway.
- The manual Web Chat UI is authenticated and available.
- No CAPTCHA, suspension, mute, or login prompt was observed in the UI state probe.

## Live Web Chat evidence

### UI/account-state probe

Observed page:

```text
URL: https://chat.deepseek.com/
Title: DeepSeek - Into the Unknown
Visible account: khos********sec@gmail.com
Textarea: Message DeepSeek
```

Classification:

```text
login_required: false
captcha_or_challenge: false
suspended_or_muted: false
chat_textarea_present: true
```

### Direct marker

Prompt submitted through the Web Chat textarea:

```text
Reply exactly: KGWM_DEEPSEEK_WEBCHAT_DIRECT_OK_20260912
```

Assistant main content returned:

```text
KGWM_DEEPSEEK_WEBCHAT_DIRECT_OK_20260912
```

Classification:

```text
DeepSeek Web Chat direct UI completion: PASS
```

### Required tool-envelope generation

Prompt submitted through the Web Chat textarea:

```text
You are behind a tool gateway. Do not explain. Reply only valid JSON exactly in this schema: {"tool_calls":[{"name":"read_file","arguments":{"path":"README.md","marker":"KGWM_DEEPSEEK_WEBCHAT_TOOL_ENVELOPE_20260912"}}]}
```

Assistant main content returned valid JSON:

```json
{"tool_calls":[{"name":"read_file","arguments":{"path":"README.md","marker":"KGWM_DEEPSEEK_WEBCHAT_TOOL_ENVELOPE_20260912"}}]}
```

Classification:

```text
DeepSeek Web Chat tool-envelope generation: PASS
```

This proves the visible Web Chat can emit a parser-compatible tool-call envelope when instructed. It does not prove that Hooshka or Kilo currently executes that tool call, because no `deepseek-web` Gateway provider is currently integrated.

### Tool-result continuation

Prompt submitted after the tool-envelope response:

```text
Tool result for read_file: {"path":"README.md","content":"# Sample Project
This repository is a test project."}
Now continue from the tool result. Reply exactly: KGWM_DEEPSEEK_WEBCHAT_TOOL_RESULT_CONTINUATION_OK_20260912
```

Assistant main content returned:

```text
KGWM_DEEPSEEK_WEBCHAT_TOOL_RESULT_CONTINUATION_OK_20260912
```

Classification:

```text
DeepSeek Web Chat tool-result continuation: PASS
```

## KiloGate-WM classification

| Gate | Result | Notes |
|---|---:|---|
| Web Chat login/account state | PASS | authenticated UI, no challenge/mute/suspension observed |
| Direct Web Chat completion | PASS | deterministic marker returned in assistant main content |
| Tool-call envelope generation | PASS | valid JSON envelope produced |
| Tool-result continuation | PASS | continuation after supplied tool result worked |
| Gateway provider integration | NOT IMPLEMENTED | no `deepseek-web` adapter/provider exists in HWG runtime |
| Kilo actual tool execution | NOT RUN | blocked by missing Gateway provider/Kilo route |
| Full agent coding certification | NOT CERTIFIED | requires integrated provider plus read/search/edit/apply_patch/shell E2 |

## Decision

DeepSeek must no longer be described as blocked by current Web Chat account state. The corrected status is:

```text
DeepSeek Web Chat manual UI E2: PASS
DeepSeek Gateway provider: NOT IMPLEMENTED
DeepSeek Kilo programming/full-agent: NOT CERTIFIED
```

The earlier local API-token failure remains useful only as evidence about `deepseek-api-kit-poc` error handling. It must not be used to classify the Web Chat route.

## Next engineering work

1. Implement a `deepseek-web` browser provider/transport in Hooshka Web Gateway.
2. Use the visible Web Chat route as the primary transport boundary.
3. Preserve provider controls: no CAPTCHA bypass, no suspension/mute bypass, no credential extraction.
4. Normalize DeepSeek reasoning/tool-envelope output into OpenAI-compatible `tool_calls`.
5. Run KiloGate-WM full-agent E2:
   - direct completion;
   - stream/reconstructed stream;
   - `read_file` tool call;
   - tool-result continuation;
   - project search;
   - edit/apply_patch;
   - restricted shell;
   - recovery/audit path.
