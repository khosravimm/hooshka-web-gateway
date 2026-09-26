# HWG Kilo / VS Code Software Project Mission Test ? E2

Date: 2026-09-26
Environment: Safe-Laptop / VS Code / Kilo Code 7.8.1 / HWG Dev 5080
Provider scope: `hooshka/deepseek-web` only
Sample workspace: `D:\Code\HWG-Kilo-Mission-E2-20260926`

## Mission

Validate the primary HWG mission using a real external coding agent: Kilo in VS Code must consume HWG's OpenAI-compatible API, use structured tools, create a non-trivial software project from an initially empty workspace, execute tests, correct failures, and complete an executable smoke scenario.

## Result

**E2 PASS WITH REMEDIATION ? not yet a clean-run certification.**

Kilo, using `hooshka/deepseek-web`, created a standard-library-only Python TaskFlow project through the HWG agent/tool loop. The produced project contains domain, JSON repository with atomic writes, service, CLI, packaging metadata, README and four unittest modules. The exact mission test command `python -m unittest discover -v` completed with **64 tests PASS**. A real CLI sequence `add -> list -> done -> search` completed with exit code 0 for every command and the final persisted JSON record was `status=done`.

The user-visible verification was repeated from the VS Code integrated terminal. Independent bounded verification produced the same result.

HWG's complete repository test suite on final Dev build `2.1.1-dev.kilo-mission-e2.20260926-1336` passed **658/658** after the final Unicode/contract cleanup and service restart.

## Defects discovered by the mission test

1. Structured agent requests carrying `tools` were being incorrectly captured by the human-chat/CAG boundary due to implicit Hooshka prompt detection. Explicit boundary flags remain authoritative, but implicit boundary activation is now bypassed for structured tool protocol requests.
2. DeepSeek Web renderer/DOM could corrupt structured tool JSON: embedded command quotes, terminal closers, missing container closers, Windows path backslashes decoded as control characters, and renderer labels around fenced code. Bounded fail-closed repairs were added only for observed unambiguous forms.
3. Assistant tool-call history was previously serialized back to the Web Chat without fenced JSON, teaching the model an unsafe continuation form that could lose dunder names such as `__init__` and `__future__`. History is now fenced.
4. Web-chat tool instructions now require one tool call per turn and explicit JSON escaping to reduce large multi-call corruption.
5. Kilo/model initially drifted from the requested domain contract and later stopped after unit tests before executing the requested smoke test. The same session was explicitly continued and corrected. This remains an agent-behavior acceptance concern, not hidden by the final PASS.

## User-visible acceptance evidence

The final verification was executed in the VS Code integrated terminal, per owner request. The project remained open in VS Code while tests and smoke commands ran.

### Unit test gate

`python -m unittest discover -v`

Result: `Ran 64 tests ... OK`.

### Real CLI smoke gate

A fresh JSON DB was used. The sequence:

- add `HWG mission task` with description
- list
- done `1`
- search `HWG mission`
- inspect persisted JSON

completed successfully. Final JSON contained exactly the mission task with `status: done` and a UTC timestamp. All command return codes were 0.

## Evidence boundary / non-claims

This evidence is scoped to Kilo 7.8.1 + DeepSeek Web + Safe-Laptop + the recorded Dev build. It does **not** certify ChatGPT, Z.ai, Grok, other accounts/models, Production 2.1.0, or a fresh-workspace first-attempt run. Because remediation occurred during the same mission, a clean rerun from a new empty workspace on the final fixed build remains mandatory before declaring the coding-agent mission fully certified.
