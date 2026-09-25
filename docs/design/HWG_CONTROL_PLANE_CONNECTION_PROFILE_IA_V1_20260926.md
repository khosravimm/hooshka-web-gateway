# HWG Control Plane Connection Profile & Navigation Contract v1.0

Date: 2026-09-26
Status: APPROVED FOR DEVELOP IMPLEMENTATION
Scope: HWG 2.1.x development Control Plane. Production 2.1.0 is not modified by this contract.

## 1. Problem statement
The prior Control Plane exposes implementation entities (Browser Runtime, Browser Profile, Account Instance, Provider, Models/Capabilities, Discovery) as peer navigation items. This obscures the operational relationship between a Web Chat, the user's account, browser state, runtime, readiness, and certification.

The owner requirement is explicit: one Web Chat Provider may have multiple user profiles/accounts. Each same-origin account must have its own isolated Browser Profile/Runtime boundary, and the panel must make it obvious which user-facing profile belongs to which account.

## 2. Canonical user-facing concept: Connection Profile
A **Connection Profile** is the user-facing aggregate used by the Control Plane. It is not the same artifact as a Provider Profile or Browser Profile.

`Provider -> Connection Profile -> Account Instance -> Browser Profile / Runtime -> Session -> Models/Capabilities -> Readiness -> Certification`

- **Provider Profile**: versioned machine-readable Provider contract/adapter knowledge.
- **Account Instance**: persistent non-secret logical identity for one account on one Provider.
- **Browser Profile**: browser storage/session isolation boundary.
- **Browser Runtime**: Chrome/CDP execution instance owning one Browser Profile.
- **Connection Profile**: user-facing aggregate binding Provider + Account + Browser Profile/Runtime into one operational identity.

The UI MUST NOT label all of these merely as “Profile”.

## 3. Multi-account contract
1. A Provider MAY have multiple Connection Profiles.
2. Two accounts on the same Provider/origin MUST NOT share one Browser Profile storage boundary.
3. A second same-origin account receives a dedicated Browser Profile and dedicated Runtime/CDP identity unless a future architecture change proves equivalent isolation.
4. Cross-origin Provider tabs may share a Browser Profile under the existing origin-isolation ADR; this is an internal optimization and MUST NOT obscure Connection Profile ownership.
5. Readiness and Certification are scoped to Provider + Account/Connection Profile + Model (+ release/environment where applicable). Evidence MUST NOT silently transfer between accounts.

## 4. Connection Profile naming UX
The system SHOULD suggest a human-readable display name after Provider/account evidence becomes available.

Suggested naming precedence:
1. `<Provider display name> — <observed account email/display identity>` when safely observable;
2. `<Provider display name> — حساب <n>` when identity is unavailable;
3. user-supplied alias.

Rules:
- `connection_profile_id` is immutable machine identity.
- `display_name` is user-facing and editable.
- A suggested name requires user confirmation or edit before becoming the chosen alias.
- Later observations MAY produce a rename suggestion but MUST NOT silently overwrite a user-confirmed name.
- Passwords, cookies, tokens, API keys, authorization headers, or equivalent secrets MUST NOT be persisted as account/profile metadata.

## 5. Primary Control Plane information architecture
1. **داشبورد** — health, alerts, next required actions.
2. **فراهم‌کننده‌ها و پروفایل‌ها** — Provider-centric view with child Connection Profiles.
3. **حساب‌ها و دسترسی** — login/session/access lifecycle and identity evidence.
4. **محیط اجرا** — advanced Browser Profile/Runtime/CDP/watchdog/supervisor operations.
5. **آمادگی و گواهی** — Explorer/Qualification/Readiness/Certification workflow.
6. **ماتریس قابلیت‌ها** — analytical Provider/Profile/Account/Model/Capability/Evidence view.

Other functions such as Interactive Chat, telemetry, API keys, settings, service operations, work register and logs remain available but are not mixed into the Provider/Profile lifecycle model.

## 6. Provider workspace contract
Each Provider MUST expose Connection Profiles as first-class children. Each Connection Profile summary SHOULD show display name, account identity/alias, access/session state, Runtime state, isolation state, model, readiness state/age, certification scope and next required action.

Primary action: **افزودن پروفایل اتصال**. The user should not need to manually create a raw Browser Profile before normal account onboarding.

## 7. Connection Profile creation workflow
1. User chooses Provider and selects `افزودن پروفایل اتصال`.
2. HWG allocates/proposes an isolated Browser Profile + Runtime as required by origin/account policy.
3. Provider target opens under the managed Runtime.
4. Live Provider view is displayed inside the same Control Plane workspace.
5. User performs genuine authority actions (login, CAPTCHA, consent, WebAuthn/native actions where required).
6. HWG evaluates account identity/session without storing secrets.
7. HWG proposes a Connection Profile display name; user confirms or edits it.
8. Account/Profile/Runtime binding is persisted.
9. Readiness/qualification continues without forcing manual reconstruction of relationships.

## 8. Integrated Explorer Live View contract
The existing integrated Provider view is retained as a core product requirement.

`one Wizard Run <-> one Browser Runtime <-> one authoritative CDP Target ID`

- Provider live target and bounded interaction remain visible beside Wizard stage/progress/evidence/next action.
- Header MUST identify Provider + Connection Profile/Account + access state + target state.
- `Page.startScreencast` is preferred when available; bounded screenshot polling remains fallback.
- Click/scroll/non-sensitive text may be relayed to the real target.
- Password fields, WebAuthn, password-manager flows, native file chooser, certain CAPTCHA/challenges, or unsafe-to-relay interactions MUST use the real Provider tab/native browser fallback.
- Native fallback MUST return to the same Wizard state/Target binding; no restart-from-zero UX.

## 9. Human Gate policy
Human Gates are reserved for genuine authority/consent/risk decisions: login, CAPTCHA/challenge, Terms/consent, destructive actions, enable/activation, or interactions that cannot safely be relayed. Explorer weakness or missing automation is not itself a valid Human Gate.

## 10. Existing requirements preserved
The redesign MUST preserve Research-first/reuse-first discovery, deterministic exploration before AI, AI output as E0/CANDIDATE until verified, visual-first action gates, commitment/retry semantics, account-scoped model entitlement, multimodal/tool qualification, progress/blocker/evidence/next-action visibility, target ownership/cleanup, no-focus-stealing, versioned contracts, and rollback protection for browser/session state.

## 11. Acceptance criteria
1. A user can create two accounts for the same Provider and distinguish their Connection Profiles immediately.
2. The two same-origin accounts use distinct Browser Profile/Runtime storage boundaries and pass a live isolation E2 scenario.
3. The panel always shows which account belongs to which Connection Profile.
4. A profile display name is suggested and can be edited/confirmed.
5. Explorer shows the real Provider target inside the same workspace while it runs, with native fallback for restricted interactions.
6. Readiness/Certification/Capability evidence is shown at the correct account/profile/model scope.
7. Raw Browser Profile/CDP details remain available for advanced operations but are not required for ordinary onboarding.
8. Primary navigation no longer presents Browser Runtime and Browser Profile as unrelated peer concepts.

## 12. Traceability
- Owner requirements: `HWG-REQ-007`, `008`, `009`, `010`, `012`, `017`, plus 2026-09-26 clarifications.
- Architecture: `docs/architecture/ADR-003-shared-window.md`.
- Integrated Live View: `docs/evidence/HWG_INTEGRATED_EXPLORER_WORKSPACE_E2_20260924.md`.
- Same-origin multi-account: `HWG-WORK-026`.
- Wizard/Live View: `HWG-WORK-029`.
- Control Plane IA/Connection Profile redesign: `HWG-WORK-030`.
