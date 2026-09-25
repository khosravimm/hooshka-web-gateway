# HWG Connection Profile / Control Plane IA — E1 Implementation Checkpoint

Date: 2026-09-26
Environment: Safe-Laptop / Dev 5080 only
Build: `2.1.1-dev.connection-profile-ia.20260926-0030`
Production 5000: untouched, remains `2.1.0`

## Implemented in this checkpoint
- Registered canonical Connection Profile domain/UX contract.
- Primary navigation changed from implementation-entity layout to mission/workspace layout:
  - داشبورد
  - فراهم‌کننده‌ها و پروفایل‌ها
  - حساب‌ها و دسترسی
  - محیط اجرا
  - آمادگی و گواهی
  - ماتریس قابلیت‌ها
- Browser Profile is no longer a peer primary-navigation concept; it remains reachable as an advanced technical view from Execution Environment.
- Provider cards now render child Connection Profiles derived from Account Instances.
- Each Connection Profile shows user-facing name, account id, access state, isolation mode and runtime binding.
- Add Connection Profile flow provisions a dedicated account runtime/profile through the existing guarded `/api/accounts` path.
- Account provisioning persists a non-secret `connection_profile` metadata object with immutable profile id, suggested/display name and confirmation state.
- User can edit/confirm Connection Profile display name through guarded PATCH endpoint.
- Provider Connection Profile action can start the dedicated runtime and open Login.
- Existing Integrated Explorer Live View is preserved; its header now includes Provider, profile context, access state and authoritative Target identity.
- Native Provider tab fallback remains the path for password/WebAuthn/native-sensitive interactions.

## Safety / scope
- No Production code, config or v2.1.0 tag changed.
- Dev restart changed only port 5080 PID; Production 5000, Desktop Agent 5181 and CDP 9330 PIDs remained unchanged.
- No real second same-origin account was provisioned in this checkpoint; `HWG-WORK-026` therefore remains PARTIAL and the multi-account isolation claim remains E1 until live E2 is performed.
- No E3 claim is made for this UI/domain change.

## Verification
- Targeted account/runtime/IA/version tests: `48 passed`.
- Full canonical suite after all changes: `633 passed`.
- `node --check control_panel_ui/panel.js`: PASS.
- Python compileall: PASS.
- Work-register JSON parse: PASS.
- `git diff --check`: PASS.
- Dev `/panel/api/meta`: version `2.1.1-dev.connection-profile-ia.20260926-0030`, branch `develop`.
- Production `/panel/api/meta`: version `2.1.0`, commit `7492991`.
- Visual review after Dev restart confirmed the new primary menu labels and build version are rendered on 5080.

## Remaining acceptance work
1. Provision a real second account for the same Provider and complete Login.
2. Prove separate Browser Profile/CDP storage/session isolation at E2 without disturbing the existing account.
3. Complete account-identity-assisted naming after login (email/display identity when safely observable) rather than relying only on the onboarding alias.
4. Extend Provider/Connection Profile cards with exact Readiness/Certification scope and age.
5. Perform scenario-based visual audit of Provider -> Connection Profile -> Account -> Environment -> Qualification navigation.
6. Human acceptance: user must distinguish two same-Provider accounts without inspecting raw ids/paths.

Primary design record: `docs/design/HWG_CONTROL_PLANE_CONNECTION_PROFILE_IA_V1_20260926.md`.
