# Hooshka Web Gateway — Web Chat Provider Integration Knowledge Transfer Playbook

- Document ID: HWG-KT-WEBCHAT-001
- Version: 1.0.0
- Status: Canonical technical knowledge-transfer playbook
- Effective date: 2026-09-18
- Scope: ChatGPT Web, Qwen Web, DeepSeek Web, Z.ai Web
- Parent architecture: HWG-ARCH-001 v1.0.0
- Parent mission: HWG-MISSION-NG-001 v1.0.0

## 1. Purpose

This document transfers the engineering knowledge accumulated while integrating and operating ChatGPT Web, Qwen Web, DeepSeek Web and Z.ai Web through Hooshka Web Gateway. Its purpose is not merely to describe the current adapters. It captures the reusable technical reasoning, provider-specific constraints, failed approaches, accepted patterns, evidence boundaries, debugging methods and onboarding procedure required to preserve the working knowledge of the current system while building the next generation of HWG.

The document must be treated as a living technical playbook. New provider discoveries, frontend changes, capability corrections, incidents and certification results must update this document or a versioned successor.

## 2. Knowledge classification

This playbook separates four knowledge classes:

- **Protocol knowledge:** request/response shape, backend endpoints, frontend controllers, SSE/WebSocket behavior and tool dialects.
- **Runtime knowledge:** browser profile, CDP ownership, authentication/session state, model/feature controls and UI lifecycle.
- **Operational knowledge:** readiness, retry, cancellation, rate/risk control, restart/recovery and observability.
- **Evidence knowledge:** what has actually passed E0/E1/E2/E3 and what remains unverified.

A historical observation is not automatically a current capability. Provider Web applications change without notice. Every reusable fact must retain its evidence date, scope and revalidation requirement.

## 3. Core architectural conclusion

The most important lesson is that a Web Chat provider is not a REST endpoint. It is a versioned execution environment consisting of:

```text
Provider Web Chat
  ├─ Account/session state
  ├─ Browser/profile/fingerprint state
  ├─ Frontend JavaScript application
  ├─ DOM and accessibility surface
  ├─ Frontend controllers/state managers
  ├─ Backend HTTP/SSE/WebSocket contracts
  ├─ Anti-bot/challenge mechanisms
  ├─ Model and feature entitlements
  ├─ Tool/Plugin behavior
  └─ Error/risk-control behavior
```

Therefore the durable unit of integration is not a selector or endpoint; it is a **versioned Provider Profile plus Account Instance plus Transport implementation plus Evidence record**.

## 4. Shared provider integration contract

Every provider integration should expose one normalized internal contract to HWG while keeping provider-specific behavior private. At minimum the provider boundary must cover:

- health/readiness;
- canonical model discovery;
- chat completion;
- streaming semantics and provenance;
- model selection;
- thinking/reasoning controls;
- search controls;
- tool-call normalization;
- file/media capabilities;
- session/conversation continuation;
- cancellation/stop;
- runtime close/recovery;
- provider risk signals;
- transport provenance and evidence metadata.

Provider-specific internals must not leak into the API, SDK or Hooshka orchestration layer.

## 5. Accepted transport hierarchy

The reusable transport hierarchy is:

```text
1. Direct provider backend HTTP/SSE/WebSocket
2. Browser-context fetch/XHR or official frontend controller
3. Browser network interception/capture
4. DOM submit/read fallback
```

This is a preference order, not a requirement to force every provider into direct HTTP. The correct transport is the least fragile, policy-compliant path that preserves the provider's legitimate session and anti-abuse controls.

### 5.1 Why backend-first matters

Backend-oriented transports reduce dependence on changing DOM structure, improve stream/state observability, make timeout phases measurable, and allow exact protocol classification.

### 5.2 Why browser state still matters

Many Web Chat providers bind session, proof, fingerprint, build/version or anti-bot state to the browser. In such cases the browser should be treated as an authenticated execution environment rather than only a graphical UI.

### 5.3 DOM is still valid

DOM remains appropriate for login, challenge handling by the human user, feature selection when no stable programmatic state exists, and final inference fallback. DOM use must be explicit and evidence-backed rather than the default shortcut.

## 6. Shared reliability rules

### 6.1 Commitment boundary

Every transport must track whether the user turn may already have reached the provider:

```text
not_sent -> maybe_sent -> committed -> terminal
```

Retry is allowed only before commitment can reasonably have occurred. Once submission may have happened, automatic replay is forbidden unless the provider exposes a proven idempotency/reconciliation mechanism.

### 6.2 Atomic agent turns

Tool definitions, system/context instructions, transcript and tool results must be presented atomically when the provider does not expose a proven native structured tool channel. Splitting the contract across multiple Web Chat turns lets the model answer before seeing the full agent protocol.

### 6.3 Stream state machine

A Web stream must distinguish at least:

```text
CONNECTING
HEADERS_RECEIVED
WAITING_FIRST_EVENT
STREAMING
TOOL_AMBIGUOUS
COMPLETED | FAILED | CANCELLED
```

Connection timeout, first-event timeout, meaningful idle timeout and total timeout are different failures and must be measured separately.

### 6.4 HTTP 200 is not success

Providers may return application errors in HTTP-200 JSON or inside a stream. Content type and application envelope must be classified before treating the response as SSE or successful completion.

### 6.5 Exact routing

Unknown provider/model identifiers fail closed. A failing provider is never silently replaced with another provider.

## 7. Shared tool protocol lessons

Tool calling through Web Chat is a normalization problem, not merely JSON parsing.

Observed provider/model outputs may include:

- strict JSON;
- fenced JSON;
- XML/QNML-style envelopes;
- DSML-like syntax;
- token/tag protocols;
- malformed Unicode/full-width markers;
- multiple JSON segments;
- Windows paths with invalid JSON backslashes.

The shared normalization pipeline should:

1. withhold ambiguous prefixes during streaming;
2. normalize known Unicode/markup corruption;
3. identify known dialects;
4. require tool names to exist in the request allowlist;
5. parse bounded balanced structures;
6. validate/coerce arguments conservatively;
7. reject missing required fields;
8. deduplicate equivalent calls;
9. apply bounded repair only for recognized protocol damage;
10. fail explicitly when tool syntax is recognized but cannot be safely parsed.

An empty tool set is never a wildcard. Tool-looking output is ordinary text unless it references a tool declared by the current request.

## 8. Shared browser/runtime rules

- Each provider/account profile is a security boundary.
- A profile has one runtime owner at a time.
- Cleanup must target explicit owned profile paths; URL-only Chrome killing is prohibited.
- CDP identity must be verified before using a runtime.
- Ordinary user browser tabs are never assumed to be HWG-owned.
- Background prompt injection/extraction must not steal desktop focus.
- Login/CAPTCHA/re-authentication may deliberately surface the browser to the user.

## 9. Shared risk-control rules

Web accounts are not load-test targets. Default policy for live Web Chat testing:

- concurrency 1;
- conservative spacing and bounded batches;
- session reuse;
- no stress/load tests;
- no account/IP rotation to evade restrictions;
- no CAPTCHA/WAF bypass;
- stop immediately on suspension/challenge/risk evidence;
- separate account-local from provider-wide failure;
- record risk evidence without exposing credentials.

A provider enforcement state is terminal for the current account until normal provider/user recovery occurs.

# Part II — Provider-specific knowledge

## 10. ChatGPT Web

### 10.1 Current architectural character

ChatGPT Web is the most mature provider integration in HWG and currently combines a browser-owned authenticated session with DOM interaction, backend-request interception and network observation where appropriate.

```text
Canonical id: chatgpt-web
CDP: 127.0.0.1:9224
Profile: .runtime\chatgpt-profile
Transport provenance: browser_ui / buffered compatibility stream
Tools: E2-proven in the certified path
Stop: provider-side Stop confirmed for the tested ChatGPT runtime path
```

### 10.2 Key implementation lessons

**Stable completion is not transient text.** ChatGPT may expose `Thinking`, partial answer nodes or React-reconciled elements while generation is still active. DOM locators can become stale because React replaces nodes. Completion logic must re-resolve the active response surface and verify stable terminal state.

**Prompt submission must be atomic.** Large agent/tool manifests must be submitted as one complete turn. Splitting protocol content across multiple UI messages created races in which the model answered before receiving the full contract.

**Efficient composer injection matters.** Character-by-character typing is slow and fragile. Prefer bounded direct fill/DOM assignment with sequential typing only as fallback, while preserving explicit submission evidence.

**Backend interception can complement DOM.** For selected cases, the authenticated frontend backend request can be intercepted/reused while preserving the legitimate browser session. The backend contract must be rediscovered and validated when the frontend changes.

### 10.3 Thinking and Search

The ChatGPT reasoning-effort control is a UI/runtime state, not a generic boolean. The tested UI could render a visible/enabled control while Playwright's normal click stability checks failed. The accepted pattern is: resolve the control near the active composer, verify visible/enabled state, use a bounded fallback interaction if necessary, then re-read the resulting state and fail closed on mismatch.

`thinking=false` means the minimum available reasoning effort in the tested UI, not proof of zero hidden reasoning. Search likewise requires observed state evidence; a request flag alone is insufficient.

### 10.4 Tool calling

ChatGPT Web demonstrated that advertised tool support is meaningless unless the full protocol is transported. HWG became agent-compatible only after serializing the full transcript, tool definitions, tool choice and tool-result continuation atomically.

Rules retained from live evidence:

- `tool_choice=required` may use one bounded protocol repair;
- auto-tool review is allowed only on strong signals;
- broad retry/review of every prose response is prohibited;
- post-submit transport failures are not replayed;
- detected-but-unparseable tool syntax is a protocol failure;
- E2 requires tool-call -> tool-result -> final-answer round trip.

### 10.5 Streaming and Stop

The current DOM-oriented ChatGPT path exposes **buffered compatibility streaming**, not native token streaming. Provenance must remain explicit.

ChatGPT is the only current provider with recorded `STOP_PROVIDER_CONFIRMED` evidence. The tested control was `button[data-testid="stop-button"]` / `aria="Stop answering"`. Certification required active generation, control activation, disappearance of active state and absence of the final marker after cancellation. Escape alone never counts as proof.

### 10.6 Failure modes to preserve in tests

- logged-out CDP profile while Gateway liveness remains healthy;
- stale React nodes;
- transient Thinking text mistaken for final output;
- model pretending a tool already ran;
- broad auto-tool review causing spurious calls;
- hidden buffering at the HTTP layer;
- backend request drift breaking interception.

## 11. Qwen Web

### 11.1 Current architectural character

Qwen provided the clearest evidence that an official Web frontend controller can serve as a backend-oriented transport without reducing the integration to DOM automation.

```text
Canonical id: qwen-web
Dedicated CDP: 127.0.0.1:9225
Profile: .runtime\qwen-profile
Current operational config: disabled
Preferred transport: browser frontend controller/backend path
Certified tool baseline: qwen:qwen3.8-max (scope-limited E2)
```

### 11.2 Backend and controller knowledge

Research and live observation identified backend patterns around user/session validation, model discovery, chat creation, completion SSE and chat cleanup. Exact paths are volatile and must be rediscovered against the current frontend.

Raw direct/browser fetch attempts encountered Alibaba/BX/WAF behavior. The successful pattern was to let the legitimate frontend retain ownership of session and anti-bot behavior while HWG invokes the frontend's own controller APIs.

```text
HWG
  -> isolated Chrome/CDP
  -> discover current frontend module/controller
  -> invoke provider-owned controller
  -> frontend performs normal backend/session/anti-bot flow
  -> HWG observes normalized state/output
```

This is materially less fragile than typing/clicking the chat DOM and is still consistent with backend-first design.

### 11.3 Dynamic module loading and commitment

Frontend module URLs/build artifacts can change and CDN imports can fail transiently. Module bootstrap is a **pre-submit phase** and may use a bounded retry budget.

Conversation creation can navigate and destroy the JavaScript execution context. The transport must distinguish bootstrap/navigation from actual user-message submission. Re-bootstrap may be safe before submit; replay is not safe afterward.

### 11.4 Thinking semantics

Provider-native semantics must be recorded instead of invented booleans. Observed Qwen modes included `Auto`, `Thinking`, and `Fast`. Tested non-thinking behavior mapped to `Fast`; thinking-enabled behavior mapped to provider-native frontend state.

The normalized HWG boolean/level and the native provider mode are separate data fields in the future Provider Profile.

### 11.5 Search and model evidence

Search is accepted only when actual frontend/backend feature state confirms it. Later E2 matrix work verified Search on/off combinations for the tested `qwen3.8-max` runtime.

Qwen also established the model-evidence rule: compare expected upstream model, frontend-selected model and backend-request model where possible. Any mismatch fails closed.

### 11.6 Tool certification is exact-scope

The large Qwen matrix showed that models and feature states cannot inherit certification from one another. Some rows passed while others failed or were held. `qwen:qwen3.8-max` retains its limited E2/Kilo tool-capable baseline, but every new explicit model/state requires independent evidence before `tool_call=true`.

### 11.7 CAPTCHA/risk handling

Human-verification events were observed during live matrix testing. Correct behavior was to pause the matrix, allow only normal manual user interaction, and mark remaining rows HOLD. The system must never automate solving or rotate accounts/proxies to evade the challenge.

### 11.8 Streaming provenance

Even though the Qwen frontend itself can receive native SSE, HWG may expose a **reconstructed** stream when deltas are derived from frontend/controller in-memory state. Provenance describes the Gateway output path, not merely an upstream implementation detail.

## 12. DeepSeek Web

### 12.1 Current architectural character

DeepSeek is integrated through a dedicated browser UI transport and isolated authenticated Chrome profile.

```text
Canonical id: deepseek-web
CDP: 127.0.0.1:9226
Profile: .runtime\deepseek-profile
Transport: browser_ui
Tools: E2 smoke certified for read/grep/write/edit/bash scope
```

### 12.2 Backend research remains useful but not automatically operational

Earlier DeepSeek work established knowledge around session creation, challenge/PoW and SSE completion. That protocol knowledge is reusable for discovery, but the production path must respect current account state and provider enforcement rather than assuming a historical backend PoC is safe for continuous automation.

### 12.3 HTTP-200 application failure

A key live observation was HTTP 200 with JSON application state indicating a muted/account-local failure instead of SSE. A legacy parser treated status 200 as successful streaming and yielded no events.

Reusable rule:

```text
HTTP status + Content-Type + application envelope
must be classified before entering the stream parser.
```

### 12.4 Account-local enforcement and risk budget

A temporary provider suspension/mute was observed after a window containing bursts of automated backend requests. The exact trigger was not disclosed. Correct classification: provider enforcement confirmed; root cause unknown; high-frequency automation is only a plausible contributing factor.

This event drove the shared controls: concurrency 1, bounded live cases, conservative spacing, no stress tests and circuit breaking on abnormal account signals.

### 12.5 UI-state detection

Searching arbitrary page text for words such as `login` caused false positives when those words existed inside user prompts. Authentication/block detection must use account/page state, active composer availability and explicit blocking signals—not transcript content.

### 12.6 React selector drift

DeepThink/Search controls were observed as `.ds-toggle-button` elements without stable native button semantics. React can replace the node during interaction. Resolve, interact, re-resolve and verify the final state.

### 12.7 Tool-envelope repair

DeepSeek sometimes emitted JSON tool envelopes containing raw Windows backslashes. The accepted repair is narrow and bounded: repair only invalid backslashes that prevent parsing of an otherwise recognizable machine envelope. Arbitrary prose must never be coerced into a tool call.

### 12.8 Post-tool final handling

After a valid `role=tool` result, a plain final answer with no additional tool call can be correct. Do not reject it merely because the original user prompt asked for a tool.

### 12.9 Stop status

Historical immediate-stop tests showed continuation to the final marker after cancellation attempts. DeepSeek must therefore remain **not provider-stop certified** until new evidence supersedes that result.

## 13. Z.ai Web

### 13.1 Current architectural character

Z.ai yielded a distinctive hybrid pattern: keep signature/CAPTCHA proof generation inside the official frontend, while capturing and parsing the actual backend completion stream.

```text
Canonical ids: zai-web and explicit zai:<model>
CDP: 127.0.0.1:9223
Profile: .runtime\zai-profile
Observed frontend build in prior evidence: prod-fe-1.1.93
Transport: browser-owned frontend + backend SSE capture
Tool baseline: glm-5.2 E2/Kilo smoke; selected other models provider/API E2 only
```

### 13.2 Backend observations

Observed completion behavior included provider-specific authorization/session context, frontend version, `X-Signature`, device identity, language/browser context, chat/message identifiers, feature flags, model selection, file/background-task data, CAPTCHA verification material and stream settings. These fields must remain provider-internal. Shared Gateway code must not synthesize provider signatures or bypass CAPTCHA.

### 13.3 Provider-owned proof delegation

The successful pattern was:

```text
Official Z.ai frontend
   -> creates provider-owned signature/proof
   -> performs legitimate completion fetch
HWG browser instrumentation
   -> observes/captures response stream
   -> parses normalized events
```

This preserves the provider's own control path while avoiding both fragile DOM answer scraping and unsafe credential/proof extraction.

### 13.4 Browser-bound state

Model discovery succeeded inside the authenticated browser context while direct host-side Python requests received HTTP 403. Browser-bound state/fingerprint may therefore be a legitimate dependency even for apparently simple read endpoints.

### 13.5 Stream phases and Deep Think

Observed stream semantics included phases equivalent to `thinking`, `answer`, and `done`. The transport should preserve this distinction internally.

Z.ai also demonstrated that capability success and continuation latency are separate dimensions. A tool operation can complete while the final text marker arrives much later in Deep Think mode. Timeout handling must not erase proven tool-execution evidence.

### 13.6 Model-selection drift

UI model options included multiline descriptions and labels that did not always match backend IDs. Future Provider Profiles must keep three fields separate:

```text
HWG canonical model id
Provider UI display label
Provider backend model id
```

### 13.7 Multiple tool segments

Z.ai can emit multiple JSON/tool-like segments in one response. First-`{` to last-`}` slicing is unsafe. Use bounded balanced-object extraction followed by request allowlist/schema validation.

### 13.8 Stop status

Historical cancellation reached the provider transport but did not prove immediate provider-side cancellation. Classification remains attempted/inconclusive until a future signed Stop Contract passes.

# Part III — Cross-provider engineering patterns

## 14. What must be standardized versus provider-specific

### Standardize in the HWG core

- canonical request/response models;
- exact routing;
- capability schema;
- provider/account/profile identity;
- stream-state vocabulary;
- commitment state;
- tool-normalization framework;
- error taxonomy;
- evidence schema;
- audit metadata;
- SDK/API contracts;
- readiness contract;
- certification workflow.

### Keep provider-specific

- DOM selectors;
- frontend modules/controllers;
- backend endpoints and payloads;
- anti-bot/session proof;
- native model names;
- native thinking/search semantics;
- native plugins/tools;
- completion-detection signals;
- stop/cancel implementation;
- quota/account restriction signals;
- file/media upload mechanics.

The abstraction should standardize **meaning and lifecycle**, not pretend the underlying mechanisms are identical.

## 15. Readiness model for the next generation

A CDP listener is not sufficient readiness. Provider/Account readiness should progress through explicit stages:

```text
RUNTIME_ABSENT
RUNTIME_STARTING
CDP_REACHABLE
PAGE_LOADING
PAGE_INTERACTIVE
AUTH_REQUIRED | AUTHENTICATED
MODEL_STATE_VALIDATING
FEATURE_STATE_VALIDATING
FUNCTIONAL_PROBE_RUNNING
READY
DEGRADED | BLOCKED | FAILED
```

READY should require a low-risk real prompt/response probe for the exact Provider Profile + Account Instance unless a documented risk policy temporarily substitutes lower evidence.

## 16. Thinking versus silence versus failure

A provider adapter must distinguish at least:

- known provider thinking/reasoning state;
- accepted request waiting for first meaningful event;
- active stream with no text because reasoning/search is ongoing;
- frontend stalled;
- backend idle timeout;
- account quota/rate wait;
- provider challenge/block;
- generation complete with empty visible text;
- transport failure.

This distinction should be expressed through normalized runtime state plus provider-specific evidence, not inferred from elapsed time alone.

## 17. Account and profile separation

Current experience supports this hierarchy:

```text
Provider Definition
   -> Provider Profile version
      -> Account Instance
         -> Browser Storage/Session
         -> Entitlements/Models
         -> Runtime State
         -> Certification Snapshot
```

Do not store account-specific capability assumptions inside the generic Provider Profile. Model access, quotas and feature entitlements can differ by account.

## 18. Observability and evidence

Default evidence should capture bounded metadata:

- timestamp;
- request/correlation id;
- provider/profile/account id;
- canonical and upstream model;
- adapter/transport/profile version;
- requested and observed feature state;
- lifecycle state;
- latency phases;
- error/risk classification;
- transport provenance;
- certification/evidence level.

Raw prompts, responses, reasoning, cookies, tokens, tool arguments/results and browser storage should not be captured by default.

## 19. Evidence ladder

Use the project evidence model consistently:

- **E0:** source/docs/research; conceptual/protocol understanding only.
- **E1:** deterministic unit/fixture/synthetic/prototype evidence.
- **E2:** real provider end-to-end evidence in a defined session/state.
- **E3:** repeated predefined runs across independent windows with explicit reliability thresholds.

A single successful Web Chat test is E2, not proof of general reliability.

## 20. Provider onboarding/recovery procedure

For a new provider or after a major frontend change:

1. Freeze current working evidence and versions.
2. Baseline account/browser state without modification.
3. Read official provider documentation and release/help material.
4. Search mature Web-to-API/open-source implementations and issue history.
5. Capture current frontend assets and network graph with non-sensitive prompts.
6. Identify model/catalog, conversation, completion, stream, stop and upload lifecycles.
7. Classify browser-bound state and anti-bot dependencies.
8. Choose the least fragile compliant transport using the shared hierarchy.
9. Implement deterministic fixtures before repeated live use.
10. Prove basic chat E2.
11. Prove model selection separately.
12. Prove Thinking/Search separately and record native semantics.
13. Prove tools with full round trip.
14. Prove streaming and classify provenance honestly.
15. Prove cancellation independently.
16. Prove restart/reconnect and account/session persistence.
17. Run interactive user certification.
18. Version Profile, Adapter, Transport, Evidence and Compatibility Manifest.

## 21. Debugging order

When a provider fails, diagnose in this order:

```text
1. Expected owned runtime running?
2. CDP identifies expected Chrome/profile?
3. Provider origin reachable?
4. Account authenticated?
5. CAPTCHA/challenge/restriction/quota signal present?
6. Expected model available and selected?
7. Requested feature state actually active?
8. Did submission begin?
9. Was request committed?
10. What backend/network event occurred?
11. Is response stream healthy?
12. Is completion detection wrong?
13. Is normalization/tool parsing wrong?
14. Is outward API/server buffering or transforming incorrectly?
```

This prevents transport bugs from being misdiagnosed as model failures and avoids unsafe replay.

## 22. Regression corpus that must survive redesign

The next generation should preserve tests for at least these learned failures:

- service Running but API unusable;
- CDP alive but logged out;
- wrong provider CDP/profile selected;
- React node replacement;
- Thinking text returned as final output;
- feature request accepted but not activated;
- unknown model silently routed elsewhere;
- empty tool list interpreted as wildcard;
- malformed tool dialect leaked as successful prose;
- valid final answer rejected after tool result;
- Windows-path JSON damage;
- multiple JSON/tool objects in one response;
- HTTP-200 JSON error misread as SSE;
- first-event versus idle-timeout confusion;
- provider risk state retried repeatedly;
- post-submit retry duplicates user turn;
- client disconnect without provider cancel attempt;
- unsafe generic SVG/DOM stop candidate;
- direct HTTP failing while browser-context path succeeds;
- UI label differing from backend model id;
- large live matrix continuing after human-verification/risk signals.

# Part IV — Provider comparison

## 23. Engineering comparison matrix

| Dimension | ChatGPT Web | Qwen Web | DeepSeek Web | Z.ai Web |
|---|---|---|---|---|
| Primary learned pattern | DOM + backend interception | Frontend controller | Controlled browser UI | Provider-owned proof + backend SSE capture |
| Dedicated CDP | 9224 | 9225 | 9226 | 9223 |
| Browser profile isolation | yes | yes | yes | yes |
| Current operational config | enabled | disabled | enabled | enabled |
| Stream provenance | buffered compatibility | reconstructed | reconstructed/buffered path | captured/reconstructed |
| Thinking control | composer reasoning effort | native feature manager/modes | UI toggle state | backend/frontend feature fields |
| Search control | UI/runtime verified | feature manager/runtime verified | UI toggle state | backend feature fields |
| Tool lesson | atomic protocol + bounded repair | exact model/state certification | narrow tolerant JSON repair | balanced multi-object parsing |
| Major risk lesson | UI drift/auth state | CAPTCHA/quota + dynamic module drift | account enforcement + false UI-state detection | signature/CAPTCHA/browser-bound proof |
| Provider-side Stop evidence | confirmed in tested path | not final-certified | negative/failed in tested path | inconclusive |

This table is a transfer aid, not a permanent capability claim. Current capability truth remains in versioned evidence and Provider Profiles.

## 24. What should not be copied forward blindly

Do not preserve implementation simply because it currently works. The next generation should preserve **knowledge and tests**, then re-evaluate mechanisms.

Candidates for redesign rather than blind copy include:

- provider-specific selectors embedded directly in large adapter classes;
- duplicated feature-state logic;
- implicit account assumptions;
- one-profile-per-provider assumptions when multi-account support is introduced;
- compatibility rendering mixed into provider transport;
- undocumented fallback chains;
- runtime behavior not represented in the Profile schema.

## 25. What must be preserved across redesign

The following are hard-earned invariants and should survive architecture changes:

- exact fail-closed routing;
- no cross-provider silent fallback;
- commitment-aware retry;
- browser/profile ownership;
- provider-local anti-abuse handling;
- bounded tool normalization;
- truthful stream provenance;
- evidence-scoped capability claims;
- separation of account-local and provider-wide failures;
- no focus stealing during normal operation;
- user-visible/manual path for login and challenges;
- metadata-first observability;
- E2 versus E3 distinction.

## 26. Knowledge-return requirement

Every future provider change must return knowledge to the project. At minimum update:

1. Provider Profile/version;
2. Adapter/Transport changelog;
3. Evidence record;
4. this playbook or its successor when a stable lesson is learned;
5. regression tests for every defect discovered;
6. architecture/ADR when the shared contract changes.

An incident fixed only in code but not captured as reusable knowledge is incomplete.

## 27. Source-of-truth references inside this repository

This playbook consolidates knowledge from, among others:

- `docs/PROVIDERS.md`
- `docs/UNIFIED_PROVIDER_ARCHITECTURE.md`
- `docs/BACKEND_FIRST_PLAYBOOK.md`
- `docs/LESSONS_LEARNED.md`
- `docs/EXPERIENCE_LOG.md`
- `docs/TOOL_BANK_EXPERIENCE_MINING_2026-09-10.md`
- `docs/WEBCHAT_FEATURE_CONTROLS.md`
- `docs/WEBCHAT_FEATURE_MATRIX_E2_2026-09-16.md`
- `docs/KILOGATE_WM_QWEN_FULL_MATRIX_2026-09-12.md`
- `docs/KILOGATE_WM_ZAI_GATEWAY_KILO_AUDIT_2026-09-12.md`
- `docs/KILOGATE_WM_DEEPSEEK_GATEWAY_KILO_AUDIT_2026-09-12.md`
- `docs/KILOGATE_WM_STOP_PROPAGATION_2026-09-12.md`
- current provider/transport source code under `adapters/` and shared protocol/runtime code under `core/`.

If a summary in this playbook conflicts with newer versioned evidence, the newer scoped evidence wins and this playbook must be updated.

## 28. Final transfer statement

The working value of the current HWG is not only that four Web Chat systems can be reached. The valuable asset is the accumulated knowledge of **how Web Chat integrations fail, how provider state must be observed, which layers should be standardized, which details must remain provider-local, and what evidence is required before a capability can be trusted**.

The next HWG generation should therefore migrate knowledge before it migrates code.
