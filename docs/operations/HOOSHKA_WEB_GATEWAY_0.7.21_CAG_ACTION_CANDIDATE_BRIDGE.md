> **SUPERSEDED ? historical evidence only (2026-09-26).**
> CAG is not an HWG subsystem. HWG does not call, embed, infer, or enforce CAG. Any caller that uses CAG must do so outside HWG and pass only generic policy/approval context to HWG when required.

# Hooshka Web Gateway 0.7.21 - CAG Action Candidate Bridge

## Scope

This release connects the Gateway agent boundary to the CAG Action Candidate API.

## Behavior

When a Hooshka-context model response contains executable/agentic output:

1. Gateway prevents raw command/code from leaving as normal chat content.
2. Gateway infers a safe Action Candidate payload.
3. Gateway POSTs the candidate to CAG `/api/action-candidates`.
4. Gateway exposes only safe metadata under `provider_meta.agent_boundary.action_candidate`.

Raw model output and held commands are not stored in the OpenAI-compatible response metadata.

## Live validation

A real `/v1/chat/completions` request against `deepseek-web` with a NaghsheYar/CAG prompt produced:

```text
boundary_delivery: safe_chat_only
hidden_executable_count: 1
action_candidate_registered: true
action_candidate_id: AC-4e11bada9d70428a
CAG candidates: 0 -> 1
contains_git_status: false
contains_curl: false
contains_systemctl: false
contains_client_access_gateway: false
```

The candidate was then dry-run through CAG 0.9.7 and produced controlled evidence.

## Test evidence

```text
Gateway Action Candidate bridge tests: 3 passed
Boundary + bridge tests: 7 passed
Gateway Full Suite: 170 passed
compileall core main.py: OK
```
