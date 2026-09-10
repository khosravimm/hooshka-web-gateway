# Hooshka Web Gateway — Development Guide

## Repository

```text
D:\Code\hooshka-web-gateway
```

Default/release branch: `master`.

## Local setup

Use the existing virtual environment for the accepted machine baseline:

```powershell
cd D:\Code\hooshka-web-gateway
.\.venv\Scripts\python.exe -m pytest -q
```

Do not casually recreate provider browser profiles; they contain runtime state and are security boundaries.

## Code map

- `main.py` — Flask/Waitress API and provider wiring
- `core/providers.py` — provider contracts/types
- `core/provider_registry.py` — registration/routing
- `core/governance.py` — auth/rate/audit controls
- `core/tool_protocol.py` — normalized tool parsing
- `core/stream_state.py` — stream state concepts
- `core/upstream_response.py` — upstream response classification
- `adapters/chatgpt_web_provider.py` — ChatGPT Web
- `adapters/qwen_web_provider.py` / `qwen_browser_transport.py` — Qwen
- `adapters/zai_web_provider.py` / `zai_browser_transport.py` — Z.ai
- `service_manager.ps1` — NSSM + owned runtime lifecycle
- `config.yaml` — tracked non-secret configuration

## Provider development workflow

1. Research provider Web behavior.
2. Prefer backend-first transport.
3. Record exact provider/frontend version evidence.
4. Build smallest provider-local adapter.
5. Add deterministic E1 tests.
6. Run `compileall`, `pytest`, `git diff --check`.
7. Perform one bounded E2 live test.
8. Record capability/provenance honestly.
9. Update docs/evidence.
10. Commit only from a clean, coherent worktree.

## New provider checklist

A new provider must define:

- `ProviderType`;
- factory/create function;
- canonical provider/model id;
- explicit capabilities;
- health behavior;
- model discovery behavior;
- completion + stream semantics;
- session/runtime ownership;
- retry/commit boundary;
- timeout model;
- error classification;
- rate budget;
- cleanup behavior;
- E1 tests;
- E2 acceptance evidence.

## Tool protocol requirements

Tool support requires schema-gated normalization. Supported parsing patterns must be based on observed evidence, not speculation.

Pipeline:

```text
canonicalize
 -> detect
 -> parse
 -> allowlist
 -> validate JSON/schema/required args
 -> dedupe
 -> assign ids
 -> emit normalized tool_calls
```

No tools declared means empty allow-list, never wildcard.

## Browser/runtime engineering rules

- one provider-owned profile per dedicated runtime;
- no reuse of unrelated personal Chrome profiles without explicit design;
- no URL-only kill/cleanup;
- no browser-token printing;
- no anti-bot bypass;
- browser lifecycle must be deterministic;
- health checks should be as non-mutating as possible.

## Test gates

Minimum before commit:

```powershell
.\.venv\Scripts\python.exe -m compileall -q .
.\.venv\Scripts\python.exe -m pytest -q
git diff --check
```

Before release:

- secret scan
- service restart
- health/ready/modes/models
- low-risk provider smoke where needed
- rollback ref
- clean worktree
- version/changelog/evidence update

## Versioning

Use semantic release intent:

- patch: fixes without changing module boundary/capability contract materially;
- minor: new provider/capability or substantial operational integration;
- major: breaking API/module/governance contract.

Never publish/tag from a dirty worktree.
