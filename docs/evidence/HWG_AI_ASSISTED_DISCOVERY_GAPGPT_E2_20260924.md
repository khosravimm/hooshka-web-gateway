# HWG AI-Assisted Discovery — GapGPT live evidence

Date: 2026-09-24
Scope: HWG-WORK-018
Target provider: `gapgpt-web`
Analyst provider/model: `deepseek-web`
Routing policy: `least_loaded`
Target-provider avoided: true
Approval: explicit, user approved

Deterministic Explorer ran first and left six icon-only controls unresolved.
AI assistance received only bounded deterministic evidence and produced six structured hypotheses.
All AI findings remained `E0 / CANDIDATE`; none was promoted directly to provider/profile truth.

The structured schema was hardened after a live malformed-JSON model response exposed a weakness.
A second live run returned six parseable hypotheses and six verification-queue items.
Safe deterministic verification then ran against the real GapGPT page:
- four focus probes returned `no_new_signal` and remained unresolved;
- two inspect probes completed with E1 observations;
- no click was executed without confirmation;
- no AI hypothesis was promoted merely because the model suggested it.

Targeted tests: 29 passed before live verification.
This record is E2 for the live AI-assist integration path; individual AI hypotheses remain E0 until independently verified.