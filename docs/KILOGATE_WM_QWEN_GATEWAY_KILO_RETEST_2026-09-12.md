# KiloGate-WM Qwen Gateway/Kilo Retest - 2026-09-12

## Correction

A manual Web Chat observation showed that Qwen can emit tool-call envelopes. The previous Qwen audit was correct only for the then-current Gateway/Kilo configuration, where Qwen tools were disabled. It must not be read as proof that Qwen Web Chat cannot produce tool calls.

This retest enables Qwen tool parsing on a test branch and evaluates `qwen:qwen3.8-max` through the KiloGate-WM E2 smoke path.

## Scope

Provider: `qwen-web`

Certified model in this retest: `qwen:qwen3.8-max`

Runtime:

```text
Qwen Web Chat via browser controller
CDP: http://127.0.0.1:9225
Default upstream model: qwen3.8-max
No provider API token path used
```

Out of scope:

- `qwen3.7-plus`, `qwen3.7-max`, `qwen3.6-plus`, `qwen3.5-plus` tool execution.
- `qwen3.5-omni-plus`; remains quarantined for Kilo until retested.
- `coder.qwen.ai`; separate application surface.
- E3/production reliability.

## Evidence files

```text
.runtime/kilogate_qwen38_provider_tool_retest_20260912.json
.runtime/kilogate_qwen38_gateway_api_tool_retest_20260912.json
.runtime/kilogate_qwen38_kilo_read_20260912.log
.runtime/kilogate_qwen38_kilo_search_20260912.log
.runtime/kilogate_qwen38_kilo_write_20260912.log
.runtime/kilogate_qwen38_kilo_edit_20260912.log
.runtime/kilogate_qwen38_kilo_bash_20260912.log
```

## Provider-level E2 result

```text
status/catalog: PASS
direct marker: PASS
required read_file tool_call: PASS
tool_result continuation: PASS
summary: 4/4 PASS
```

Key markers:

```text
KGWM_QWEN38_TOOL_RETEST_20260912_DIRECT_OK
KGWM_QWEN38_TOOL_RETEST_20260912_TOOLCALL_OK
KGWM_QWEN38_TOOL_RETEST_20260912_TOOLRESULT_OK
```

## Gateway API E2 result

Dev endpoint used for retest:

```text
http://127.0.0.1:5005/v1
```

Result:

```text
api_direct: PASS
api_required_tool: PASS
api_tool_result: PASS
summary: 3/3 PASS
```

Key markers:

```text
KGWM_QWEN38_API_TOOL_RETEST_20260912_DIRECT_OK
KGWM_QWEN38_API_TOOL_RETEST_20260912_TOOLCALL_OK
KGWM_QWEN38_API_TOOL_RETEST_20260912_TOOLRESULT_OK
```

## Kilo tool execution result

Temporary Kilo provider used for retest:

```text
hooshka-qwen-dev/qwen:qwen3.8-max
```

Verified tools:

```text
read: PASS
grep/search: PASS
write: PASS
edit: PASS
bash/shell: PASS
```

Markers:

```text
KGWM_KILO_QWEN38_READ_OK_20260912
KGWM_KILO_QWEN38_SEARCH_OK_20260912
KGWM_KILO_QWEN38_WRITE_OK_20260912
KGWM_KILO_QWEN38_EDIT_OK_20260912
KGWM_KILO_QWEN38_BASH_OK_20260912
```

The Kilo runs executed real local tools. The edit/bash probe used only `.runtime/kilogate_qwen_patch_probe.txt`.

## Protocol hardening from Web Chat screenshots

The retest adds parser support and regression coverage for Web-chat outputs that are not clean single JSON but still contain explicit tool-call intent, including:

```text
<tool_call>{"name":"edit","arguments":{...}}</tool_call>
<tool_call>read<arg_key>filePath</arg_key><arg_value>...</arg_value></tool_call>
```

This is a tolerance layer for explicit tool-call wrappers only. It is not a permission to treat arbitrary prose as a tool call, and it does not allow fabricated tool results.

## Certification statement

```text
qwen:qwen3.8-max = KiloGate-WM E2 tool-capable smoke certified
```

Certified scope:

```text
Provider-level tool-call generation
Gateway API tool-call round-trip
Kilo read/search/write/edit/bash tool execution
```

Not certified:

```text
Other explicit Qwen models for tools
qwen3.5-omni-plus
coder.qwen.ai
E3/production reliability
```

## Configuration rule

`qwen-web` may resolve to the certified `qwen3.8-max` baseline for tool-capable Kilo use. Explicit Qwen models other than `qwen:qwen3.8-max` must not be marked `tool_call=true` in Kilo until they receive their own KiloGate-WM tool-execution evidence.
