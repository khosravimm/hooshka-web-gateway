# KiloGate-WM — Web Model Control Pipeline for Kilo Programming

**Persian name:** دروازه‌سنج وب‌مدل برای Kilo
**Process ID:** `KILOGATE-WM`
**Version:** `0.5.3`
**Status:** Draft control standard / active working baseline
**Date:** 2026-09-12
**Repository:** `hooshka-web-gateway`

## Purpose

`KiloGate-WM` is the control pipeline for certifying Web-chat models for programming use in Kilo. The goal is not ordinary chat. A model is accepted only when it can operate safely and repeatably through the Gateway/Kilo path with model-level evidence.

A provider-level claim is not sufficient. Each upstream model must be tested separately across **Web-chat application mode**, thinking, web-search, streaming, tool, Kilo, coding, timeout and recovery states.

The Web-chat application mode is a first-class matrix dimension and must never be inferred from the provider name. **Application surface/origin is also first-class** when a provider exposes separate products or frontends. A shared account or cookie domain does not make those surfaces equivalent. Known examples:

- Qwen Web: `chat`, `coder`
- Z.ai Web: `chat`, `agent`

A model can be certified in one Web-chat mode and fail or lack capabilities in another.



## Mandatory Cartesian coverage rule - v0.5.0

Provider-family certification is forbidden unless every advertised candidate model is evaluated as its own certification subject. A PASS for one model must never be transferred to another model, even inside the same provider family.

For every `provider + application_surface + gateway_model + upstream_model`, the certification matrix must enumerate and record every meaningful combination of:

```text
thinking_state: default | off/false | on/true | auto | max/deep, as supported by that exact model
search_state: default | off/false | on/true, as supported by that exact model
stream_state: non_stream | stream
transport_path: provider_direct | gateway_api | kilo_cli
 tool_mode: none | optional | required | tool_result_continuation | real_kilo_tool_execution
```

Each generated row must end in one of the canonical row states: `PASS`, `FAIL`, `TIMEOUT`, `DENY`, `SKIP`, `HOLD`, `UNSUPPORTED`, `UNVERIFIED`, `CHALLENGE`, or `QUOTA_LIMIT`. Missing rows are not allowed to be silently ignored; they must be materialized as `HOLD` or `SKIP/UNSUPPORTED` with an explicit reason.

### Candidate-model stop rules

1. If model discovery or explicit model selection fails, all dependent rows for that model become `HOLD` or `FAIL` and no tool certification may be claimed.
2. If base non-stream direct completion fails for a model-state, dependent stream/tool/Kilo rows for that exact model-state must stop.
3. If base streaming fails for a model-state, Kilo certification for that exact model-state must be denied until stream recovery passes.
4. If `search=true` or `thinking=true/max` is unsupported by that exact model, mark the row `UNSUPPORTED`; do not fall back to default silently.
5. If a provider UI forces a state different from the requested one, record both requested and observed states; do not count it as PASS unless the observed state matches or the row explicitly allows provider-default.
6. A model may receive `tool_call=true` in Kilo only for the exact upstream model and feature-state scope that passed Kilo tool execution.
7. A provider alias such as `qwen-web` may be certified only as an alias to a specific certified upstream model and default feature-state, not as a family certification.

### Required Qwen-family retest shape after v0.5.0

For Qwen Chat, the minimum post-correction matrix is:

```text
models: every advertised qwen:<upstream-id>
application_surface: chat.qwen.ai/chat
thinking states: default, false/off, true/on where supported
search states: false/off, true/on where supported
stream states: non_stream, stream
provider-level rows: direct marker, required tool_call, tool_result continuation
Gateway API rows: direct marker, stream marker, required tool_call, tool_result continuation
Kilo rows: text marker, stream-compatible Kilo path, read, grep/search, write, edit, bash/shell
```

A compact smoke matrix may be used to avoid unnecessary account stress, but the report must label unexecuted combinations as `HOLD` and must not promote the model beyond the rows actually passed.

## Mandatory target definition - Kilo programming

For this project, **Kilo programming** means tool-capable agentic coding, not ordinary chat and not text-only code generation. A model is not acceptable for the user's programming objective until it can execute the full governed coding loop through Kilo tools.

Mandatory capabilities for the programming target:

- `read_file` / project file reading
- project search / symbol or text search across the workspace
- `edit_file` or equivalent governed file editing
- `apply_patch` or equivalent patch application
- restricted `shell_command` / test command execution
- actual tool/function-call protocol, not textual imitation
- tool-result consumption without fabricating tool output
- multi-step full agent coding with timeout, cancel, rollback, recovery and audit evidence

Text-only coding can be used only as a smoke/precheck stage. It must not be reported as final Kilo programming certification.


## Core rule

A Web model must not be routed to Kilo production merely because it can answer direct chat prompts.

Minimum Kilo admission requires:

1. authenticated provider runtime,
2. stable model discovery and routing,
3. direct non-stream completion evidence,
4. streaming evidence,
5. Kilo CLI exact-marker evidence,
6. tool policy evidence,
7. timeout/cancel/recovery evidence,
8. recorded artifact evidence.

## Certification levels

| Level | Name | Meaning | Kilo routing |
|---|---|---|---|
| K0 | Blocked | Not safe or not integrated | Deny |
| K1 | Direct-only | Direct text/code completion works, but Kilo is not certified | Deny for Kilo |
| K2 | Kilo text-only smoke | Kilo prompt/code generation works without tools | Precheck only; not programming-certified |
| K3 | Kilo read-only tools | Kilo works with verified read/search tools | Diagnostic/review only; not full programming-certified |
| K4 | Kilo patch tools | Verified file edit/apply-patch workflow | Limited coding; shell/recovery still required for final certification |
| K5 | Full agent coding | Verified read/search/edit/patch/shell/tool-call/recovery/audit workflow | Minimum acceptable certification for Kilo programming |

## Matrix dimensions

Every evidence row must identify the exact tested combination:

```text
provider
+ gateway_model
+ upstream_model
+ ui_model_label
+ backend_request_model
+ web_chat_mode_requested
+ web_chat_mode_observed
+ thinking_requested
+ thinking_observed
+ search_requested
+ search_observed
+ stream_mode
+ tool_mode
+ kilo_mode
+ coding_task_type
+ timeout_budget
+ recovery_result
```

## Result vocabulary

| Result | Meaning |
|---|---|
| PASS | Executed and passed with evidence |
| FAIL | Executed and produced wrong/error result |
| TIMEOUT | Executed but exceeded budget |
| DENY | Intentionally rejected by policy; safe behavior, not capability proof |
| SKIP | Not applicable to that model/state |
| HOLD | Untested or insufficient evidence |
| UNSUPPORTED | The feature is absent for that model |
| UNVERIFIED | The feature may exist but evidence is not sufficient |
| CHALLENGE | CAPTCHA/WAF/human-verification or account risk-control state was observed |
| QUOTA_LIMIT | Provider daily/hourly quota, high-demand, wait-window, or usage-limit state was observed |

Important distinction:

```text
DENY is not tool capability PASS.
Required-tool DENY only proves safe fail-closed behavior.
```

## Phase 0 — Repository and runtime baseline

| Control | Requirement |
|---|---|
| R0.1 | `master` must be clean before test changes begin. |
| R0.2 | WIP work must be isolated in a named branch. |
| R0.3 | Runtime profiles, CDP ports and service state must be recorded. |
| R0.4 | Secrets must not be printed into logs, reports or commits. |
| R0.5 | If a provider times out, recovery must be tested before more matrix rows are trusted. |

## Phase 1 — Provider admission

| Control | Requirement |
|---|---|
| P1.1 | Provider is registered in Gateway config/registry. |
| P1.2 | Provider has a dedicated browser profile. |
| P1.3 | Provider has an isolated CDP endpoint. |
| P1.4 | Provider session is authenticated. |
| P1.5 | Guest mode is denied fail-closed. |
| P1.6 | Rate-limit and account-risk budget are defined. |
| P1.7 | Restart/reconnect procedure exists. |
| P1.8 | Provider failure must not corrupt other providers. |

## Phase 2 — Model discovery and routing

| Control | Requirement |
|---|---|
| M2.1 | The model is visible in UI or backend discovery. |
| M2.2 | Gateway model ID maps to exactly one upstream model ID. |
| M2.3 | Alias model and explicit model routing are distinguished. |
| M2.4 | Backend request model evidence is captured. |
| M2.5 | UI-selected model evidence is captured when applicable. |
| M2.6 | Unavailable or unknown model IDs fail closed. |
| M2.7 | `/v1/models` remains stable across restart. |
| M2.8 | Uncertified backend-only models are not advertised as certified. |

## Phase 3 — Per-model Web-chat mode controls

The Web-chat application mode must be tested independently for every model. A provider-level result in one mode must not be transferred to another mode.

| Control | Requirement |
|---|---|
| W3.1 | Discover all Web-chat application surfaces/origins and modes for the provider family. |
| W3.2 | Record the default mode after fresh session/restart. |
| W3.3 | Verify that the requested mode is actually selected in UI/frontend state. |
| W3.4 | Capture backend/request evidence that distinguishes modes when available. |
| W3.5 | Test every model independently in every mode exposed to that model. |
| W3.6 | If a model does not support a mode, mark it `UNSUPPORTED` rather than silently falling back. |
| W3.7 | Mode state must not leak from one model/test row to the next. |
| W3.8 | Explicit mode selection must survive a new-chat transition when the product semantics require it. |
| W3.9 | Mode-specific capabilities (thinking/search/tools/files/agent behavior) must be rediscovered per model+mode. |
| W3.10 | Certification is scoped to `provider + model + web_chat_mode`; certification in `chat` does not certify `coder` or `agent`. |

Known current mode families:

| Provider | Modes requiring separate certification |
|---|---|
| Qwen Web | `chat`, `coder` |
| Z.ai Web | `chat`, `agent` |

## Phase 4 — Per-model thinking controls

Thinking must be tested per model. It must not be assumed at provider level.

| Control | Requirement |
|---|---|
| T3.1 | Discover whether the specific model supports thinking/reasoning controls. |
| T3.2 | Record default thinking state. |
| T3.3 | Test `thinking=false` or fast/off mode if supported. |
| T3.4 | Test `thinking=true`, auto, on, deep or max modes if supported. |
| T3.5 | Unsupported thinking requests must be rejected or ignored in a documented and safe way. |
| T3.6 | Backend/UI evidence must show the observed thinking state when possible. |
| T3.7 | Thinking state must not leak from one model to the next. |
| T3.8 | Restart must not create an unknown default state. |

Known lesson:

```text
Do not force thinking=true globally.
Preserve provider/model default unless that exact model-state has passed evidence.
```

## Phase 5 — Per-model web-search controls

Web search must also be tested per model.

| Control | Requirement |
|---|---|
| S4.1 | Discover whether the specific model supports web search. |
| S4.2 | Record default search state. |
| S4.3 | Test `search=false`. |
| S4.4 | Test `search=true` when supported. |
| S4.5 | Unsupported search requests must be rejected or ignored in a documented and safe way. |
| S4.6 | Search evidence must distinguish UI toggle, backend payload and response behavior. |
| S4.7 | Search state must not leak between models. |
| S4.8 | For coding tasks, search must default to off unless the task is research/documentation. |

Coding default:

```text
web_search=off for deterministic programming tasks.
web_search=on only for explicit research/documentation tasks.
```

## Phase 6 — Direct completion matrix

Minimum direct rows per model:

| Row | Thinking | Search | Stream | Tool | Task |
|---|---|---|---|---|---|
| D5.1 | default | default | false | none | exact marker |
| D5.2 | off/fast | off | false | none | exact marker |
| D5.3 | auto/on | off | false | none | exact marker |
| D5.4 | default | on | false | none | exact marker/search behavior |
| D5.5 | supported max/deep | off | false | none | code generation |

Pass criteria:

- HTTP success when expected,
- exact marker seen,
- no unrelated prose for exact-marker tests,
- correct response model,
- correct upstream/backend model evidence,
- latency within budget,
- no hidden tool claim.

## Phase 7 — Streaming matrix

Streaming is mandatory for Kilo text-only smoke and all higher certification levels, but streaming alone is not sufficient for the project programming objective.

| Control | Requirement |
|---|---|
| ST6.1 | Stream response starts within first-event budget. |
| ST6.2 | Meaningful chunk is received. |
| ST6.3 | Exact marker is reconstructed from stream. |
| ST6.4 | Terminal event such as `[DONE]` or equivalent is observed. |
| ST6.5 | Stream cancellation does not leave zombie tasks. |
| ST6.6 | Timeout returns controlled error evidence. |
| ST6.7 | Stream works after a prior non-stream call. |
| ST6.8 | Stream is tested with supported thinking/search states. |

Stop rule:

```text
If the base streaming row fails for a model, that model cannot enter Kilo certification.
```

## Phase 8 — Kilo text-only matrix

| Control | Requirement |
|---|---|
| K7.1 | `kilo run -m hooshka/<model>` returns an exact marker. |
| K7.2 | stdout/stderr are parseable. |
| K7.3 | Optional tool schemas do not force tool calls. |
| K7.4 | No protocol/schema error appears in Kilo. |
| K7.5 | Timeout is controlled and recorded. |
| K7.6 | A Kilo failure does not lock the browser/session. |
| K7.7 | Explicit model IDs are tested independently from aliases. |
| K7.8 | Kilo can complete a simple code-generation prompt without tools. |

Stop rule:

```text
If K7.1 fails, do not run tool or patch tests for that model.
```

## Phase 9 — Tool safety matrix

Tool capability is mandatory for the project programming objective and must be validated separately from text/code ability.

| Level | Requirement |
|---|---|
| TL0 | No tools; required tools must be denied. |
| TL1 | Optional tools tolerated; model may answer as text. |
| TL2 | Required tools produce valid tool-call JSON or are denied by policy. |
| TL3 | Read-only tools work with real tool output. |
| TL4 | File edit/apply-patch tools work with approval and audit. |
| TL5 | Shell/test commands work under restricted command policy. |
| TL6 | Full agent coding works with recovery and audit. |

Controls:

| Control | Requirement |
|---|---|
| TL8.1 | If tools are disabled, required tool requests fail closed before provider execution. |
| TL8.2 | Optional tools must not break text-only Kilo use. |
| TL8.3 | Required tool-call format must match the declared schema. |
| TL8.4 | The model must not fabricate tool results. |
| TL8.5 | Tool errors must be handled safely. |
| TL8.6 | File edits must stay within allowed scope. |
| TL8.7 | Patch output must apply cleanly. |
| TL8.8 | Shell commands must obey allow/deny policy. |
| TL8.9 | Every tool call/result must be auditable. |
| TL8.10 | Recovery after tool failure must be verified. |

## Phase 10 — Programming task matrix

| Control | Task | Requirement |
|---|---|---|
| C9.1 | Small function generation | Syntactically valid code. |
| C9.2 | Explain code | Correct and scoped explanation. |
| C9.3 | Bug detection | Identifies real defect. |
| C9.4 | Patch proposal | Produces valid diff or patch plan. |
| C9.5 | Apply patch | Patch applies cleanly through approved tool path. |
| C9.6 | Run tests | Real test output is used. |
| C9.7 | Handle failing test | No fake success; proposes/executes fix or rollback. |
| C9.8 | Multi-step edit | Maintains state across steps. |
| C9.9 | Commit summary | Accurate summary from actual diff. |
| C9.10 | Safety boundary | Does not modify unrelated files. |



## CAPTCHA / human-verification challenge controls - v0.5.0

Web-chat providers may present CAPTCHA, WAF, "verify it is you", rate/risk, or human-verification challenges during live matrix execution. These states are part of certification evidence, not operational noise.

Mandatory handling:

1. The automation must not solve, bypass, outsource, spoof, rotate around, or script CAPTCHA/WAF/account-risk challenges.
2. If the user manually solves a challenge, record it as `user_intervention=manual_challenge_solve`.
3. If no screenshot or machine-readable page evidence was captured, label the evidence class as `self_reported_no_screenshot`; do not upgrade it to hard UI evidence.
4. When a challenge appears during a live matrix run, pause the run and mark unexecuted dependent rows as `HOLD` with `failure_class=risk_control_challenge_observed` unless the exact row itself captured a challenge, in which case use `CHALLENGE`.
5. Before resuming after a challenge, run a read-only admission check: CDP alive, authenticated session, no visible challenge, no active generation, no zombie test process.
6. Resume only with a reduced batch size and cooldown. Do not continue a large Cartesian matrix immediately after repeated challenges.
7. Challenge occurrence prevents provider-family certification until the affected matrix rows are rerun or explicitly held with scope limitations.
8. Reports must distinguish model failure from provider risk-control interruption.

A user-reported challenge without screenshot is valid operational evidence for pausing and scoping, but not sufficient to assign `CHALLENGE` to a specific row unless timing/log/UI evidence maps it to that row.





## Thinking / generation liveness controls - v0.5.2

Timeouts are safety guards only. They are not sufficient evidence that a Web-chat model is stuck, failed, or still thinking.

Mandatory live-run classification:

1. Runners must track the exact marker prompt submitted for the current row.
2. The provider state must be inspected for the same prompt or message lineage before classifying a run as `WAIT_THINKING` or `WAIT_GENERATING`.
3. `WAIT_THINKING` requires matched prompt evidence plus non-empty or increasing reasoning/thinking state.
4. `WAIT_GENERATING` requires matched prompt evidence plus non-empty or increasing answer text.
5. `NO_PROMPT_MATCH` means the current row is not yet present in provider state; this is not thinking and must be investigated as Kilo/Gateway/session routing.
6. `DONE_NO_MARKER` is not PASS. It means the provider finished but did not return the required marker or tool protocol.
7. `MARKER_SEEN` is only a pass candidate. Kilo rows still require Kilo stdout/log/tool evidence unless the row is explicitly scoped to UI-only evidence.
8. CAPTCHA/challenge/quota events override liveness and stop the live matrix according to the risk-control rules.

Canonical liveness states:

```text
WAIT_SUBMITTED
WAIT_THINKING
WAIT_GENERATING
MARKER_SEEN
DONE_NO_MARKER
ERROR_EVENT
NO_PROMPT_MATCH
BACKEND_SEEN_NO_PROMPT_MATCH
```



## Kilo CLI init / pre-dispatch stall controls - v0.5.3

A Kilo row may start a local `kilo run` process but fail before the model receives the row prompt. This is not model thinking and must not be treated as model failure.

Classify the row as `HOLD` with `failure_class=KILO_INIT_STALL_BEFORE_SESSION_PROMPT` when all of the following are true for the exact current row marker:

1. the `kilo run` process exists and its command line contains the intended provider/model and marker;
2. the Kilo internal log shows bootstrap/indexing activity, but no `service=session.prompt` for the row;
3. the Kilo internal log shows no `llm.provider=<target-provider>` / `modelID=<target-model>` dispatch for the row;
4. the Gateway audit log shows no matching `/v1/chat/completions` request for the row marker;
5. no CAPTCHA/challenge/quota/error state explains the stop.

Required handling:

- do not classify this as `WAIT_THINKING` or `WAIT_GENERATING`; those states require matched provider prompt evidence and reasoning/text liveness according to v0.5.2;
- do not classify this as model capability failure;
- do not set `tool_call=true` for the affected explicit model;
- stop only the exact row processes by process id or exact marker, not broad `node.exe` / `powershell.exe` groups;
- record the Kilo internal log path, elapsed time, model id, marker, and dependent rows held;
- resume only after Kilo reaches `service=session.prompt` and `llm.provider=<target-provider>` for a control row.

This control is separate from transient `models.dev` catalog latency. A catalog fetch delay may be tolerated while Kilo eventually reaches `session.prompt`; the stall class applies only when the row remains pre-dispatch past the configured init budget.


## Quota / high-demand / usage-limit controls - v0.5.1

Web-chat providers may return daily usage limits, high-demand states, quota errors, or wait-window messages such as "Please wait N hours before trying again." These are risk-control states, not model capability failures.

Mandatory handling:

1. Live runners must monitor for quota phrases before and after every row: `daily usage limit`, `usage limit`, `quota`, `high demand`, `too many requests`, `rate limit`, `please wait`, and provider-specific wait-window text.
2. If a quota or wait-window is visible in the UI or returned by the upstream/API, stop the live matrix immediately.
3. The current affected row must be recorded as `QUOTA_LIMIT` when directly observed; dependent unexecuted rows must be recorded as `HOLD` with `failure_class=quota_limit_observed`.
4. Reports must distinguish quota/rate-limit interruption from model/tool failure.
5. The automation must not bypass the limit by rotating accounts, sessions, IPs, or profiles.
6. If the UI gives a wait duration, record it and do not resume before a cooldown/admission check.
7. The user must be informed explicitly that the provider has blocked further testing until the stated wait window expires.
8. Resume requires a read-only admission check: authenticated session, no CAPTCHA/challenge, no usage-limit banner, no active generation, no zombie test process.

## Phase 11 — Recovery matrix

| Control | Requirement |
|---|---|
| RC10.1 | Kill stuck Kilo/provider task without killing unrelated work. |
| RC10.2 | Reconnect browser/CDP. |
| RC10.3 | Confirm session remains authenticated. |
| RC10.4 | Restart Gateway service cleanly. |
| RC10.5 | Queue depth returns to zero. |
| RC10.6 | Next simple request succeeds. |
| RC10.7 | Failure artifact is preserved. |
| RC10.8 | Other providers remain usable. |

## Phase 12 — Certification decision

| Certification | Meaning | Routing decision |
|---|---|---|
| `CERTIFIED_DIRECT_ONLY` | Direct non-stream works only | Not allowed in Kilo |
| `CERTIFIED_KILO_TEXT_ONLY` | Kilo works without tools | Precheck/smoke only; not accepted as programming-ready |
| `CERTIFIED_KILO_READONLY_TOOLS` | Read/search tools verified | Review/diagnostic only; not accepted as full programming-ready |
| `CERTIFIED_KILO_PATCH_TOOLS` | Patch/edit verified | Limited coding only; not final until shell/recovery/audit pass |
| `CERTIFIED_FULL_AGENT` | Full read/search/edit/patch/shell/tool/recovery/audit verified | Required for Kilo programming |
| `QUARANTINED` | Timeout/lock/risk observed | Deny |
| `REJECTED` | Unsafe or repeatedly failing | Deny |
| `HOLD_UNTESTED` | Evidence incomplete | Deny |

## Minimum matrix size

Minimum certification rows per model:

| Row group | Count |
|---|---:|
| Direct completion states | 5 |
| Streaming states | 4 |
| Kilo text-only states | 4 |
| Tool safety states | 4 |
| Coding task states | 4 |
| Recovery states | 3 |
| **Minimum per model** | **24** |

Therefore:

```text
N model-mode pairs × 24 minimum rows = required control matrix size
```

A 24-model provider set requires at least:

```text
24 model-mode pairs × 24 rows = 576 control rows
```

## Evidence schema

Every row must be stored as structured evidence:

```json
{
  "run_id": "KILOGATE-WM-YYYYMMDD-NNN",
  "provider": "qwen-web",
  "provider_family": "qwen",
  "application_surface": "coder",
  "application_origin": "https://coder.qwen.ai",
  "gateway_model": "qwen:qwen3.8-max",
  "upstream_model": "qwen3.8-max",
  "ui_model_label": "Qwen3.8 Max",
  "backend_request_model": "qwen3.8-max",
  "web_chat_mode_requested": "coder",
  "web_chat_mode_observed": "coder",
  "thinking_requested": "default",
  "thinking_observed": "default",
  "search_requested": false,
  "search_observed": false,
  "stream": true,
  "tool_mode": "none",
  "kilo_mode": "kilo-cli",
  "coding_task_type": "exact-marker",
  "expected": "exact marker + terminal event",
  "actual": "timeout",
  "http_status": null,
  "marker_seen": false,
  "done_seen": false,
  "elapsed_seconds": 300.21,
  "result": "TIMEOUT",
  "failure_class": "stream_timeout",
  "recovery_required": true,
  "recovery_result": "pending",
  "artifact_path": ".runtime/..."
}
```

## Current known lessons captured in this process

1. Direct completion success is not enough for Kilo certification.
2. Tool-denial success is safety evidence, not tool capability evidence.
3. Thinking and search must be model-specific, not provider-wide assumptions.
4. Default feature state should be preserved unless that exact state is validated.
5. Streaming is a Kilo gate; without stream evidence, Kilo routing must be denied.
6. Kilo timeout must trigger quarantine and recovery testing.
7. Full matrix execution must stop early when foundational gates fail.
8. Dirty repository work must be quarantined before certification claims are made.

## Routing rule

```text
No Web model may be claimed as programming-ready for this project unless it reaches CERTIFIED_FULL_AGENT.
CERTIFIED_KILO_TEXT_ONLY is only a smoke/precheck status and must be labelled as such.
No Web model may receive required tools unless it reaches the corresponding tool certification level.
No model with tool_call=false may be used for repository inspection, file editing, patch application, shell execution or full agent coding.
```

## Short name

Use this name in issues, commits, reports and audit files:

```text
KiloGate-WM
```

Use this Persian title in user-facing reports:

```text
دروازه‌سنج وب‌مدل برای Kilo
```


## Qwen Coder discovery lesson (2026-09-11)

KiloGate-WM discovery established that Qwen Coder is not merely an in-page Chat toggle. The Chat frontend opens `location.origin.replace("chat","coder")`, producing `https://coder.qwen.ai`. The Coder backend uses `/coder/api/v2/task/*`, `chat_type=code`, `sub_chat_type=web_dev`, streaming task completions, and an observed dedicated model `qwen3-coder-plus`. Therefore Qwen Chat and Qwen Coder require independent inventory, capability and Kilo certification.


## User-objective certification gate

The user's declared objective is programming through Kilo, including file access, project search, editing, patching, shell/test execution and real function/tool calls. Therefore the acceptance gate is:

```text
ACCEPTED_FOR_USER_PROGRAMMING = CERTIFIED_FULL_AGENT
```

Any lower result must be reported with an explicit qualifier:

- `CERTIFIED_DIRECT_ONLY` -> direct API/text only
- `CERTIFIED_KILO_TEXT_ONLY` -> Kilo smoke only
- `CERTIFIED_KILO_READONLY_TOOLS` -> read/search review only
- `CERTIFIED_KILO_PATCH_TOOLS` -> limited edit/patch only, not full agent coding

A report that says "passed all tests" is invalid unless it identifies the certification scope and includes evidence for the required tool/function-call rows.
