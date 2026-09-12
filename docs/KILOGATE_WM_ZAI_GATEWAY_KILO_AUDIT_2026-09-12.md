# KiloGate-WM Z.ai Gateway/Kilo Audit - 2026-09-12

## Scope

Target: Z.ai Web Chat through Hooshka Web Gateway and Kilo CLI.

This audit certifies the Web Chat path, not a direct Z.ai API. The runtime is a dedicated browser/CDP session.

## Runtime

- Provider: `zai-web`
- Dedicated CDP runtime: `127.0.0.1:9223`
- Browser profile: project-owned `.runtime/zai-profile`
- Frontend observed: `prod-fe-1.1.93`
- Authenticated Web Chat session: PASS
- Model used for certification: `zai:glm-5.2`
- Gateway alias `zai-web` resolves to the evidence-backed `glm-5.2` baseline for this certification.

## Deep-think timing policy

Z.ai runs in Deep Think mode and may take materially longer than ordinary chat providers.

KiloGate-WM therefore used:

- launch timeout: 120 s
- first-event timeout: 240 s
- idle timeout: 300 s
- total timeout: 600 s

A timing overrun without contradictory evidence is classified as `TIMEOUT/INCONCLUSIVE`, not as a model capability failure.

Capability and reliability are evaluated separately.

## E1 deterministic gate

Targeted Z.ai/tool-protocol suite: `22 passed`.

Full repository suite: `85 passed`.

`git diff --check`: PASS.

## Provider-level Web Chat E2

Evidence: `.runtime/kilogate_zai_glm52_provider_e2_20260912.json`.

Results: direct marker PASS; required tool-call envelope PASS; tool-result continuation PASS; summary 3 PASS / 0 FAIL.

Provider-level edit was separately verified in required and auto modes. Both returned `finish_reason=tool_calls` with tool `edit`.

## Gateway API E2

Evidence: `.runtime/kilogate_zai_gateway_api_e2_20260912.json`.

Development endpoint: `http://127.0.0.1:5003/v1`.

Results: direct marker PASS; required tool-call PASS; tool-result continuation PASS; summary 3 PASS / 0 FAIL.

## Kilo E2 tool execution

Temporary provider: `hooshka-zai-dev/zai-web`.

Verified real Kilo tool execution:

- read: PASS
- grep/search: PASS
- write: PASS
- edit: PASS
- bash/shell: PASS

For edit, Kilo evidence showed `tool=edit`, `status=completed`, `Edit applied successfully`, and the probe file changed from `KGWM_ZAI_PATCH_BEFORE_20260912H` to `KGWM_ZAI_PATCH_AFTER_20260912H`.

For shell, Kilo executed `Get-Content .runtime/kilogate_zai_patch_probe.txt -Raw` with `tool=bash`, `status=completed`, `exit=0`, and output `KGWM_ZAI_PATCH_AFTER_20260912S`.

## Kilo integration finding

Kilo sends `tool_choice=auto` and a broad tool set. In the observed edit request the offered set contained 14 tools. Provider-only edit tests with a single edit tool already passed, so the model capability existed before the Kilo integration fix.

The Gateway now adds a bounded explicit-tool hint only when the user explicitly names exactly one offered tool. This improves selection inside the broad Kilo tool set without changing the external API semantics from `auto`.

## Parser hardening

Z.ai can emit multiple JSON/tool segments in one response. The parser now extracts the first balanced JSON object instead of using a naive first-`{` / last-`}` span.

The provider can also accept a raw final answer after an actual tool result when no further tool is required, while malformed apparent tool requests remain fail-closed.

## Reliability finding

Some Deep Think runs completed the actual tool operation but delayed the final text marker for a long period.

Therefore:

- tool capability: PASS
- final-continuation latency/reliability under Deep Think: variable
- E3 / production reliability: NOT CERTIFIED

A slow final continuation must not be reported as failure of the tool operation when Kilo evidence proves the operation completed.

## Certification

`zai-web` / `zai:glm-5.2` is accepted as `KiloGate-WM E2 TOOL-CAPABLE SMOKE CERTIFIED` for read, grep/search, write, edit, and bash/shell.

This is not an E3 or production-reliability certification.

## Model-selection limitation

The Z.ai UI model selector showed inconsistent behavior for some explicit models during this audit. `glm-5.2` was the model with reproducible selection/runtime evidence and is the certification baseline.

Other advertised Z.ai models must not inherit this certification automatically. Each requires independent model-level evidence.

## Main service / final Kilo verification

After merge, `HooshkaWebGateway` was restarted on the production-local endpoint `http://127.0.0.1:5000`. `/ready` reported `zai-web` ready.

Kilo was then configured so only the evidence-backed entries `hooshka/zai-web` and `hooshka/zai:glm-5.2` have `tool_call=true`; the temporary `hooshka-zai-dev` provider was removed.

Final Kilo verification on the main provider passed:

```text
model: hooshka/zai-web
tool: read
status: completed
file: README.md
marker: KGWM_KILO_MAIN_ZAI_READ_OK_20260912B
exit: 0
error: none
```

The Z.ai UI showed the request in `Deep Think / Max` and later returned the exact final marker. This confirms the long delay was model thinking latency rather than a transport or tool failure.


## GLM-5.3 / GLM-5.3-Flash retest - 2026-09-12

A follow-up retest was performed after the initial certification because `zai:glm-5.3` and `zai:x-preview-l` / `GLM-5.3-Flash` had previously failed at explicit model selection.

Root cause of the earlier failures: the Z.ai model selector options include multi-line descriptions after the display name. The adapter was matching the whole visible text, and later an already-open menu state plus JavaScript regex escaping caused selector failures. The selector was hardened to:

- skip clicking the selector button when the menu is already open;
- choose model options by the first visible line of the option button;
- avoid JavaScript regex escaping for newline splitting;
- normalize the Z.ai UI label `GLM-5.3-Flash` to backend id `x-preview-l` for model-evidence validation.

Provider-level retest evidence:

```text
.runtime/kilogate_zai_glm53_flash_retest_20260912.json
.runtime/kilogate_zai_glm53_flash_retest2_20260912.json
```

Provider-level results:

```text
zai:glm-5.3: direct marker PASS; required read_file tool_call PASS; tool-result continuation PASS; summary 3/3 PASS.
zai:x-preview-l / GLM-5.3-Flash: direct marker PASS; required read_file tool_call PASS; tool-result continuation PASS; summary 3/3 PASS.
```

Gateway API retest evidence:

```text
.runtime/kilogate_zai_glm53_flash_api_retest_20260912.json
```

Gateway API results on dev endpoint `http://127.0.0.1:5004/v1`:

```text
zai:glm-5.3: api_direct PASS; api_required_tool PASS; api_tool_result PASS; summary 3/3 PASS.
zai:x-preview-l / GLM-5.3-Flash: api_direct PASS; api_required_tool PASS; api_tool_result PASS; summary 3/3 PASS.
```

Certification boundary: this retest upgrades `zai:glm-5.3` and `zai:x-preview-l` to provider/Gateway API E2 tool-call PASS. It does not automatically mark them as Kilo full tool-execution certified, because Kilo `tool_call=true` remains enabled only for `hooshka/zai-web` and `hooshka/zai:glm-5.2` until a separate Kilo read/search/write/edit/bash run is completed for each explicit model.
