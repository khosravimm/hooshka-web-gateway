# HWG Public Cancellation API — E2

Date: 2026-09-24
Scope: HWG-WORK-009
Evidence level: E1 + E2

## Implemented
HWG exposes `POST /v1/chat/cancel` as the canonical public cancellation API.
The caller may target an explicit Provider or a known `conversation_id`; conflicting targets fail closed.
Python and TypeScript reference SDKs expose the same cancellation operation.
OpenAPI publishes the endpoint and the compatibility manifest classifies cancellation as normalized.

## DeepSeek user-view discovery
The first E2 attempt returned `cancelled=false`: the provider UI exposes no textual Stop label.
User-view observation showed the composer primary/circle control transitions from disabled Send to an enabled square Stop control while generation is active.
The DeepSeek cancellation hook now recognizes this state only when the composer textarea is empty, preventing accidental send of a user draft.

## E2 proof
A long DeepThink request was started through candidate HWG and cancelled through the public API.
Cancellation response: HTTP 200, `supported=true`, `cancelled=true`, `method=composer_primary_stop`.
The in-flight chat request terminated with HTTP 409 and error type `generation_cancelled`.
The error retained `commitment_state=committed` and `retry_allowed=false`; no hidden replay occurred.

## Remaining WORK-009 gap
Public cancellation is operational and covered by both SDKs.
WORK-009 remains PARTIAL because explicit Profile/Account targeting in inference is still open.