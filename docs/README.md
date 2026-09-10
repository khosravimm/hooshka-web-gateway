# Documentation Index

Start here for the operational and architectural record of `mcp-web-bridge`.

- `../VERSION` — current project version.
- `../CHANGELOG.md` — versioned change history.
- `TEST_EVIDENCE_2026-09-10.md` — E1/E2 evidence for the 0.3.0 ChatGPT Web operational baseline.
- `EXPERIENCE_LOG.md` — append-only dated findings and incidents.
- `LESSONS_LEARNED.md` — stable lessons promoted from operational experience.
- `AWA_REUSE_AUDIT_2026-09-10.md` — what was learned/reused from `D:\Code\ai-web-adapter`, with independent-validation status.
- `TOOL_BANK_EXPERIENCE_MINING_2026-09-10.md` — source-inspected experience mining from the `D:\Tools` research bank, including Qwen, DeepSeek, Gemini, Grok, FreeLLMAPI, WebAI-to-API and OmniRoute.
- `BACKEND_FIRST_PLAYBOOK.md` — executable discovery and implementation policy: direct backend first, browser-context fetch second, network capture third, DOM fallback last.
- `UNIFIED_PROVIDER_ARCHITECTURE.md` — target architecture for ChatGPT Web, DeepSeek Web, Qwen Web and Z.ai Web behind one API.
- `ARCHITECTURE.md` — earlier architecture notes; use the unified architecture document for current provider-routing invariants.
- `USAGE.md` — API usage examples.
- `CONTROL_PANEL.md` — control-panel documentation.
- `WINDOWS_SERVICE_NSSM.md` — Windows/NSSM operational notes.

## Evidence rule

A document or historical source can motivate a change, but runtime claims are made only from evidence reproduced in this repository. E1 = deterministic synthetic/unit/fixture evidence, E2 = real Web Chat end-to-end evidence, E3 = repeated predefined reliability thresholds across independent time windows.
