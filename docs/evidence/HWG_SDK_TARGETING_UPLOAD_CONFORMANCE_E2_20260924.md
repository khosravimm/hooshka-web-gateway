# HWG SDK Targeting + Upload Conformance — E2

Date: 2026-09-24
Scope: HWG-WORK-009
Evidence level: E1 + E2

## Completed SDK contract
Both reference SDKs now cover the required HWG agent-facing capabilities:
- authentication/header support
- Chat Completions
- streaming
- Responses API
- capability / provider / contract discovery
- structured errors
- canonical media upload + delete
- Provider / Profile / Account selection
- public cancellation
- tool payload pass-through via canonical request fields

Profile/Account targeting is resolved against the persistent NG inventory and fails closed on unknown or mismatched provider/profile/account relationships.
Dedicated second-account runtime proof remains governed by HWG-WORK-026 and is not claimed by this record.
## Live E2 markers
Python SDK target selection:
- request target: `deepseek-web / deepseek-web:default / deepseek-web:default-account`
- exact response: `HWG_TARGET_E2_P3A7`
- response metadata reproduced the exact provider/profile/account target.

TypeScript SDK target selection:
- exact response: `HWG_TS_TARGET_E2_Q4B8`
- response metadata reproduced the exact provider/profile/account target.

Python canonical upload:
- `POST /v1/uploads` via SDK → opaque upload ID
- upload ID supplied to targeted Chat request
- exact file-only marker returned: `HWG_PY_UPLOAD_E2_H7C2`
- upload deletion confirmed.

TypeScript canonical upload:
- exact file-only marker returned: `HWG_TS_UPLOAD_E2_J8D4`
- upload deletion confirmed.

Responses API target selection:
- exact response: `HWG_RESP_TARGET_E2_R5C9`
- response metadata reproduced the exact provider/profile/account target.
## Public cancellation E2
DeepSeek live cancellation returned:
- cancel endpoint: HTTP 200
- `supported=true`
- `attempted=true`
- `cancelled=true`
- `method=composer_primary_stop`

The original in-flight request then terminated as:
- HTTP 409
- `type=generation_cancelled`
- `commitment_state=committed`
- `retry_allowed=false`
- no hidden replay.

## Verification
- Python full suite: `488 passed`
- TypeScript typecheck: PASS
- TypeScript contract tests: PASS
- Python compileall: PASS
- `git diff --check`: PASS

Result: HWG-WORK-009 exit criteria are satisfied at E1 + E2 for the reference SDK contract and Candidate HWG runtime.