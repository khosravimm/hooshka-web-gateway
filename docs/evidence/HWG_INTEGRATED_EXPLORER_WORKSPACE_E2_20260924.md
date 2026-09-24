# HWG Integrated Explorer Workspace — E2 Limited Evidence

Date: 2026-09-24
Scope: Dev Control Plane `127.0.0.1:5080`; NoteGPT target; production port 5000 untouched.

## Problem
The URL-driven Wizard and the Provider browser tab were visually and operationally separated. Users had to move between windows and could lose track of which tab the Explorer was observing.

## Architecture decision
Do not iframe arbitrary Providers. Instead keep the real Provider tab under the existing Browser Runtime/CDP and render an integrated live view beside the Wizard.

Workspace contract:
- left: live Provider target view and bounded user interaction;
- right: Wizard stage, visual state, evidence, next action, and progress;
- both sides bind to one Browser Runtime and one CDP Target ID.

Current E2 transport is bounded screenshot polling. This is intentionally a limited implementation; `Page.startScreencast` is the intended production-grade streaming direction after latency/resource evaluation.

## Live verification
NoteGPT URL: `https://notegpt.io/`

Observed in the Control Plane:
- live pane became visible immediately after Observe was requested;
- initial status: `در حال ساخت Target واقعی Provider...`;
- activity banner remained visible concurrently;
- live image connected to target `EA61E9BB6DA514BF5504287624A3F662`;
- live pane was physically left of the Wizard pane in the rendered UI;
- screenshot: `.runtime-dev/wizard-activity-evidence/integrated-note-gpt-workspace-v2.png`.

Target interaction verification used a second NoteGPT target `3F82D0C6A881BDB2C41BF654E1A3CDFB`:
- click was dispatched through `/provider-wizard/live-input` to the real target;
- text marker `HWG_LIVE_INPUT_E2` appeared exactly in the real Composer;
- no submit/send action was invoked;
- marker was removed with `Control+A` + `Backspace`;
- final Composer was empty.

## Safety boundaries
- Password-field text injection is blocked by the backend with `sensitive_input_requires_native_tab`.
- The actual Provider tab remains available as fallback for password managers, WebAuthn, native file chooser behavior, or challenges that cannot be safely relayed.
- No Provider enable operation is performed by this workspace.
- Input dispatch is target-bound; URL fallback exists only for target lookup during bootstrap.

## Related state-machine fixes
This checkpoint also removes two passive dead ends found during NoteGPT exploration:
- `auth_ambiguous` can resolve to `ACCESS_AVAILABLE` from safe same-origin session/user endpoints without claiming authenticated identity;
- committed-but-unverified Qualification now runs an actual read-only diagnosis step without resend, instead of merely promising later analysis.

## Verification
- targeted onboarding/live-view tests: PASS;
- full canonical `.venv` suite: `576 passed`;
- `compileall`: PASS;
- `node --check control_panel_ui/panel.js`: PASS;
- `git diff --check`: PASS.

## 2026-09-25 extension — compact shell, CDP screencast, target lifecycle
- Sidebar evidence dump removed; UI shows product version `1.0.0-dev.7` and compact build identity `develop · bf79cc5`.
- Wizard-owned target lifecycle E2: target was opened with `owned_by_wizard=true`, closed through `/provider-wizard/close-target`, and was no longer present in the live CDP page set.
- CDP screencast E2 on NoteGPT: frame sequences `1`, `2`, `6` were observed from `Page.startScreencast`, with JPEG frame sizes `54122`, `54081`, `54129` bytes.
- Stream stop returned sequence `8`; the same Wizard-owned target was then closed successfully.
- Screenshot polling remains only as bounded fallback when screencast transport is unavailable.
