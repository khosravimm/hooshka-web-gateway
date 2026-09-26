# HWG Connection Profile Unified Workflow — E1/E2 Checkpoint

Date: 2026-09-26  
Build: `2.1.1-dev.connection-profile-workflow.20260926-0140`  
Environment: Safe-Laptop Dev `5080` only

## Scope

This checkpoint advances `HWG-WORK-030` without changing Production `5000` or tag `v2.1.0`.

Implemented workflow:

`Provider -> Connection Profile -> Account -> dedicated/shared Runtime -> Explorer Live View -> Readiness / exact-scope Certification`

## Implemented

- Dedicated Account runtimes from the persistent Account inventory are first-class `/panel/api/browser-runtimes` entries with `scope=account`, `account_id`, Connection Profile name, CDP, port and profile path.
- Existing Connection Profiles can enter Explorer directly. The selected Account runtime is preselected and the Live View scope carries Provider, Connection Profile/Account and access state.
- Creating a new Connection Profile now provisions the isolated Account, starts its Runtime and opens the login surface as one guided flow.
- Provider and Accounts workspaces expose exact-scope certification metadata from a read-only certification-matrix endpoint.
- Certification remains account/model scoped. The DeepSeek default Account shows `E3_PASS_SCOPED`; the E2 secondary Account explicitly remains uncertified.
- No Explorer qualification/send action is triggered by merely navigating from a Connection Profile.

## Live verification

Narrow E2 routing verification used the already-qualified real secondary DeepSeek Connection Profile:

- Account: `deepseek-web:e2-secondary-20260926`
- Runtime: `http://127.0.0.1:9340`
- Browser Profile: dedicated/exclusive
- Access: `AUTHENTICATED`
- Provider-to-Explorer routing selected the exact `9340` runtime.
- Explorer URL resolved to `https://chat.deepseek.com/`.
- Explorer scope fields were populated with the human-readable profile name, exact Account ID, and `AUTHENTICATED`; the existing Integrated Explorer E2 remains the evidence for visible/interactable Live View itself.
- Visual artifact: `.runtime-dev/connection-profile-e2/unified-workflow-provider-to-explorer.png`.

The certification UI was also verified conservatively:

- `deepseek-web:default-account` -> `E3_PASS_SCOPED`
- `deepseek-web:e2-secondary-20260926` -> `گواهی نشده`

This does **not** grant E2/E3 to other providers, accounts, models, or the new generalized workflow as a whole.

## Safety / non-regression

Dev service restart changed only port `5080` process ownership. During the checkpoint:

- Production `5000`: unchanged
- Desktop Runtime Agent `5181`: unchanged
- shared CDP `9330`: unchanged
- secondary DeepSeek CDP `9340`: unchanged

No credentials, cookies, access tokens, or other secrets were written to evidence.

## Evidence level

- **E1**: generalized Connection Profile workflow implementation and deterministic tests.
- **E2 (bounded)**: live Provider -> secondary DeepSeek Connection Profile -> exact dedicated Explorer runtime routing and visual scope verification.
- **Not claimed**: generalized multi-provider E2, human acceptance completion, or any additional provider E3.

`HWG-WORK-030` therefore remains `IN_PROGRESS`.
