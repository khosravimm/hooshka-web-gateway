# HWG URL-Driven Provider Onboarding Wizard — E2

Date: 2026-09-24
Scope: WORK-025 / Control Plane usability and provider onboarding

## User-facing rule
The initial user input is only the Web Chat URL. HWG proposes identity, runtime and adapter strategy. Technical fields such as provider type, provider id and priority are not initial user inputs.

## Live E2 — unknown provider
URL: `https://chat.mistral.ai/chat`

Observed through the live Control Plane and shared Browser Runtime:
- suggested name: `Mistral`
- suggested id: `mistral-web`
- adapter: no existing adapter matched
- recommendation: discovery candidate
- user-view state: `login_required`
- visible evidence: `Sign in`
- page title: `Vibe Chat`
- visible controls observed: 10–13 across repeated observations
- editable input observed: 1
- candidate persisted under `.runtime-dev/provider-onboarding/mistral-web.json`
- provider config was not polluted with an unexecutable provider type

The live UI instructed the user to complete Login/Terms in the visible browser and then use `دوباره بررسی کن`.
## Live E2 — existing provider origin
URL: `https://chat.deepseek.com/`

The wizard detected that the origin is already registered as `deepseek-web` and recommended reusing that Provider. It did not offer creation of a duplicate operational Provider; the registration action remained disabled and the UI directed the user toward Account/Session when a second identity is needed.

## User-view verification
The Control Plane was exercised by real clicks through Chrome/CDP:
1. Providers → Add
2. URL entry
3. Analyze/propose
4. User-view observation
5. Result/next-action rendering

The old `Provider type`, `Provider id`, and `priority` inputs are absent from the wizard.
