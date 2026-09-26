> **SUPERSEDED ? historical evidence only (2026-09-26).**
> CAG is not an HWG subsystem. HWG does not call, embed, infer, or enforce CAG. Any caller that uses CAG must do so outside HWG and pass only generic policy/approval context to HWG when required.

# Hooshka Web Gateway 0.7.20 — Agent Boundary Fix

## Scope

This release fixes the Hooshka/CAG chat boundary at the Gateway level, not only in Command Center.

## Fixed

- Adds a Hooshka/CAG context boundary before sending requests to Web Chat providers.
- Defines CAG as **Hooshka Controlled Action Gateway**, not Client Access Gateway.
- Prevents executable shell/code snippets and UI artifacts from leaving `/v1/chat/completions` as normal human chat content when Hooshka context is detected.
- Buffers streaming Hooshka-context responses at the Gateway boundary before safe-chat delivery to prevent partial command leakage.
- Stores only safe classification metadata under `provider_meta.agent_boundary`; raw held command/code is not stored in response metadata.

## Runtime validation

Service restarted successfully:

```text
HooshkaWebGateway PID: 25140 -> 9348
Version: 0.7.20
Health: OK
```

Live `/v1/chat/completions` probe against `deepseek-web` with a NaghsheYar/CAG prompt produced:

```text
boundary_delivery: safe_chat_only
boundary_policy: hooshka_wg_agent_boundary_v1
hidden_executable_count: 1
contains_client_access_gateway: False
contains_systemctl: False
contains_journalctl: False
contains_curl: False
contains_copy: False
contains_download: False
```

## Test evidence

```text
Boundary tests: 6 passed
Full Gateway suite: 167 passed
compileall: OK
```
