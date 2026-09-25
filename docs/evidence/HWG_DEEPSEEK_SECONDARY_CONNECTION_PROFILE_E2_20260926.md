# HWG DeepSeek Secondary Connection Profile — E2 Evidence

Date: 2026-09-26
Environment: Safe-Laptop / Dev Control Plane 5080
Build: `2.1.1-dev.connection-profile-ia.20260926-0120`
Scope: `deepseek-web` multi-account Connection Profile isolation only.

## Result

E2 PASS for real same-origin multi-account isolation and lifecycle.

Two live DeepSeek accounts were maintained concurrently:

- default: `deepseek-web:default-account` on shared CDP `9330`;
- secondary: `deepseek-web:e2-secondary-20260926` on dedicated CDP `9340`.

Both were independently `AUTHENTICATED` after the user completed login for the secondary account.

## Isolation evidence

- default Browser Profile: `.runtime-dev\shared-profile`;
- secondary Browser Profile: `.runtime-dev\accounts\deepseek-web__e2-secondary-20260926`;
- secondary sharing mode: `exclusive_profile`;
- Browser Profile paths are distinct;
- secondary runtime uses unique CDP port `9340`;
- three independent DeepSeek browser-state fingerprints (`userToken`, user-info state, and last-session state) were compared only as SHA-256 fingerprints in-memory and all differed between 9330 and 9340;
- raw secrets/tokens were not persisted in evidence;
- persisted raw evidence stores only boolean distinctness results.

Raw bounded evidence:
`.runtime-dev/connection-profile-e2/deepseek-two-account-isolation-e2.json`

## Lifecycle verification

The secondary Account Runtime was restarted through the account-scoped Runtime Agent route.

Observed after restart:

- CDP port remained `9340`;
- Browser Profile path remained the dedicated secondary path;
- secondary account returned `AUTHENTICATED` with high-confidence evidence (`composer_visible` + `account_identity_visible`);
- default DeepSeek account remained `AUTHENTICATED`;
- shared CDP `9330` remained unchanged;
- Production `5000` remained unchanged.

## Classifier correction discovered during E2

This run exposed an important provider behavior: DeepSeek can show a composer in guest/anonymous mode. Therefore `composer visible` alone is not sufficient authentication evidence.

The blind/session classifier was hardened fail-closed:

- composer without strong identity evidence => `UNKNOWN` with login interaction required;
- Account Lifecycle maps this to `LOGIN_REQUIRED` for governed account onboarding;
- composer plus a visible masked account identity => `AUTHENTICATED` with high confidence.

This prevents Guest mode from being accepted as a valid HWG Account session.

## Control Plane visual verification

The Provider workspace was inspected live after reload. The DeepSeek Provider card showed:

- `Connection Profiles 2`;
- `deepseek-web:default-account` — `AUTHENTICATED`;
- `DeepSeek — حساب دوم E2` / `deepseek-web:e2-secondary-20260926` — `AUTHENTICATED`;
- default isolation `cross_origin_isolated`;
- secondary isolation `exclusive_profile`;
- secondary Runtime `http://127.0.0.1:9340`;
- visible `+ افزودن پروفایل اتصال` action.

Visual artifact:
`.runtime-dev/connection-profile-e2/deepseek-two-connection-profiles-card.png`

## Scope boundary

This E2 proves real multi-account isolation and account-scoped runtime lifecycle for DeepSeek on Safe-Laptop Dev. It does not claim multi-account E2 for other Providers and does not change the Production 2.1.0 certification scope.
