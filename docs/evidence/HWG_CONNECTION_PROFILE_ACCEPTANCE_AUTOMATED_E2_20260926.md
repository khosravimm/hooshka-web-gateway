# HWG Connection Profile Acceptance — Automated E2 Scenario Audit

Date: 2026-09-26  
Build: `2.1.1-dev.connection-profile-acceptance.20260926-0920`  
Environment: Safe-Laptop Dev `5080` only

## Purpose

Prepare `HWG-WORK-030` for human acceptance without substituting automated UI evidence for human approval.
The user journey under audit is:

`Provider -> Connection Profile -> Account -> Login/Access -> Explorer Live View -> Readiness -> exact-scope Certification`

## Defect found and corrected

Migrated default Connection Profiles did not carry a dedicated account runtime. The Provider workspace could render them, but `Continue in Explorer` could not resolve a runtime because it only searched account-scoped CDP mappings.

The Explorer selection now resolves in this order:

1. exact Account runtime,
2. exact account-declared CDP,
3. owning shared Provider runtime.

Dedicated Account runtimes still win first and therefore preserve same-origin multi-account isolation.

## Automated live routing evidence

The following existing Connection Profiles were routed through the UI after the Dev service restart:

| Provider / Account | Runtime selected | Access shown in Explorer | Observation result |
| --- | --- | --- | --- |
| `chatgpt-web:default-account` | shared `9330` | `AUTHENTICATED` before observe; live observation reported `ready` | real Provider target connected; S1 remained incomplete |
| `zai-web:default-account` | shared `9330` | `AUTHENTICATED` before observe; observation reported `auth_ambiguous` | target did not become a completed qualification surface in this bounded run |
| `grok-web:default-account` | shared `9330` | `UNKNOWN` before observe; observation reported `auth_ambiguous` | real Provider target connected; Candidate observation recorded |
| `deepseek-web:default-account` | shared `9330` | `AUTHENTICATED` before observe; observation reported `quota_limited` | Screencast started; S1 remained incomplete |
| `deepseek-web:e2-secondary-20260926` | dedicated `9340` in prior bounded E2 | `AUTHENTICATED` | exact-account routing already evidenced; no broader certification claim |

This is routing / UI-observation evidence only. It does **not** promote Z.ai, Grok, ChatGPT, or the DeepSeek secondary account to E3.

## Human-readable identity

Default migrated accounts now use a human-readable fallback label such as:

- `ChatGPT — حساب اصلی`
- `Z.ai — حساب اصلی`
- `Grok — حساب اصلی`
- `DeepSeek — حساب اصلی`

The raw Account ID remains available as a secondary technical identifier.

The Provider workspace shows a human `محیط اتصال` value (`مشترک Provider` or `اختصاصی این حساب`) and moves raw CDP/Profile details under collapsed `جزئیات فنی`.

## Fail-closed Readiness correction

A secondary dedicated account must not invoke the Provider-level Readiness endpoint because that endpoint probes the Provider/default account runtime. The Accounts workspace now disables that action for non-default accounts and explicitly states that an account-scoped readiness probe is still required.

This prevents a misleading readiness result from being attached to the wrong identity.

## Verification

- Dev service restarted after each code change and the visible API build advanced to `2.1.1-dev.connection-profile-acceptance.20260926-0920`.
- JavaScript syntax check passed.
- Targeted Connection Profile / version / relationship / browser-runtime tests passed.
- Full repository test suite is executed before commit.
- Production `5000` remains `2.1.0`; no Production code or tag is modified.

## Evidence level

- **E1**: generalized UX/runtime selection, human-readable labels, collapsed technical details, fail-closed secondary readiness action.
- **E2 bounded**: automated UI routing across real existing default Connection Profiles and existing real Provider browser sessions.
- **Not yet complete**: explicit human acceptance, account-scoped readiness endpoint for dedicated secondary accounts, generalized qualification success across all providers.

`HWG-WORK-030` remains `IN_PROGRESS`.
