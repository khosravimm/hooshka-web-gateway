# HWG Unified Provider Wizard IA — E1/E2 Checkpoint

Date: 2026-09-26  
Build: `2.1.1-dev.unified-provider-wizard.20260926-1040`  
Environment: Safe-Laptop Dev `5080` only

## Decision

Provider Wizard start and Provider Wizard status/resume are one workflow and one workspace, not separate product capabilities.

Target UX:

`Exploration & Preparation -> New Web Chat OR Resume Existing Qualification -> same Provider Wizard -> Live View -> Stage/Evidence -> Readiness/Certification`

## Implemented

- Removed the large `wizard-candidate-card` from the Providers/Connection Profiles workspace.
- Added a single `کاوش و آماده‌سازی Provider` entry in the Discovery/Preparation workspace.
- Added `+ افزودن Web Chat جدید` as the new-Wizard entry point.
- Moved existing Candidate stage/state/evidence controls into that same workspace.
- Added `ادامه در Wizard` for resuming an existing Candidate.
- Provider page `کاوش / افزودن Provider` now routes to the unified workspace instead of opening a separate new-provider form directly.
- Wizard close/cancel returns to the unified Exploration/Preparation workspace.

## Bounded E2 visual scenario

Using the existing real `grok-web` Candidate:

- Providers page contained no live Wizard candidate card.
- Unified workspace showed both New Web Chat and Resume actions.
- Candidate state remained `S4 / PARTIAL`, `DISABLED_PROVIDER_REGISTERED` (no status inflation).
- Resume opened the same Provider Wizard with:
  - URL: `https://grok.com/`
  - Runtime: shared CDP `9330`
  - Connection Profile: `Grok — حساب اصلی`
- Visual artifact: `.runtime-dev/connection-profile-e2/unified-provider-wizard-1040-final.png`

## Evidence classification

- **E1**: IA unification, routing, deterministic tests.
- **E2 bounded**: real Grok Candidate resume into the same Wizard/Runtime on Dev 5080.
- **Not claimed**: Human Acceptance completion, broader provider qualification success, or new E3.

Production `5000` / release `2.1.0` was not changed.
