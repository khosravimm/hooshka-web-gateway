# KiloGate-WM Qwen Audit — 2026-09-11

## Scope

Provider: `qwen-web`

Application surfaces:

- `chat.qwen.ai` / `chat`
- `coder.qwen.ai` / `coder` discovered separately; not yet exposed through a Gateway provider.

Primary objective: certify Qwen Web Chat models for Kilo Code use through the local OpenAI-compatible Gateway.

## Evidence files

Runtime evidence is stored under `.runtime/` and intentionally remains outside Git-tracked source:

- `kilogate_qwen_chat_explicit_direct_matrix_20260911.json`
- `kilogate_qwen_chat_explicit_direct_matrix_summary_20260911.json`
- `kilogate_qwen_stream_coding_matrix_20260911.json`
- `kilogate_qwen_stream_coding_matrix_summary_20260911.json`
- `kilogate_qwen_kilo_cli_full_after_stream_fix_20260911.json`
- `kilogate_qwen_kilo_cli_full_after_stream_fix_summary_20260911.json`

## Chat/direct non-stream result

Matrix dimensions:

- explicit models: `qwen3.7-plus`, `qwen3.8-max`, `qwen3.7-max`, `qwen3.6-plus`, `qwen3.5-plus`, `qwen3.5-omni-plus`
- thinking: default, false, true
- web search: false, true
- stream: false
- tool mode: none

Result:

```json
{"rows": 30, "pass": 28, "pass_deny": 2, "fail": 0}
```

The two `PASS_DENY` rows are the expected fail-closed result for `qwen3.5-omni-plus` with `thinking=true`. Discovery showed that this model has no Thinking capability.

## Stream/Kilo-coding result

Matrix dimensions:

- explicit models: `qwen3.7-plus`, `qwen3.8-max`, `qwen3.7-max`, `qwen3.6-plus`, `qwen3.5-plus`, `qwen3.5-omni-plus`
- thinking: false
- web search: false
- stream: true

Result:

```json
{"rows": 6, "pass": 6, "fail": 0}
```

## Kilo CLI result

Kilo command form:

```text
kilo.exe run -m hooshka/<model> "Reply exactly: <marker>"
```

Result:

```json
{"rows": 6, "pass": 5, "fail": 1}
```

Certified for Kilo:

- `hooshka/qwen:qwen3.7-plus`
- `hooshka/qwen:qwen3.8-max`
- `hooshka/qwen:qwen3.7-max`
- `hooshka/qwen:qwen3.6-plus`
- `hooshka/qwen:qwen3.5-plus`

Quarantined for Kilo:

- `hooshka/qwen:qwen3.5-omni-plus`

Reason: `qwen3.5-omni-plus` passed direct and Gateway SSE tests but timed out in the Kilo CLI path after 160 seconds and required Qwen runtime recovery. Therefore it remains explicit-API accessible but must not be advertised as Kilo-operational until re-certified.

## Important implementation conclusions

1. A provider-level certification is insufficient. Qwen model capability differs per upstream model.
2. Thinking selection must be model-aware:
   - `Auto` when available,
   - `Thinking` when `Auto` is unavailable,
   - `Fast` for `thinking=false` when available,
   - fail-closed `unsupported_feature` when the requested feature is unsupported.
3. Readiness/model discovery must not race active Playwright completion work; transport-level locking is required.
4. Failed/cancelled browser streams must reset the Qwen transport to avoid poisoning later requests.
5. `coder.qwen.ai` is a separate application surface and requires a separate provider/adapter before Kilo certification.

## Certification statement

Qwen Chat is certified for Kilo Code text/coding smoke use for five explicit models listed above. `qwen-web` alias remains available, but certification should prefer explicit models to prevent accidental upstream drift. `qwen3.5-omni-plus` is not Kilo-certified.
