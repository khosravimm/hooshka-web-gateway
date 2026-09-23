# HWG Embedded Chat Canonical Upload — E2

Date: 2026-09-23
Scope: HWG-WORK-007 / HWG-WORK-025
Evidence level: E1 + E2

## Implemented capability
HWG now exposes a canonical temporary upload lifecycle:
- `POST /v1/uploads` accepts multipart files and returns opaque upload IDs.
- Local storage paths are not returned to clients.
- Uploads are bounded by count/size and expire by TTL.
- `DELETE /v1/uploads/{upload_id}` removes temporary payloads.
- Chat APIs accept `upload_ids`; HWG resolves them server-side into provider file paths.
- Existing media certification is enforced before provider dispatch.

Embedded Chat now uses this canonical API rather than local file paths or a panel-only upload path.
## E2 canonical API proof
Artifact marker: `HWG_EMBEDDED_UPLOAD_E2_R9F3`

Observed flow:
`/v1/uploads → opaque upload_id → /v1/chat/conversation → DeepSeek Web → assistant response`

Result:
- Upload HTTP: 201
- Conversation HTTP: 200
- Exact assistant response: `HWG_EMBEDDED_UPLOAD_E2_R9F3`
- Commitment state: terminal
- Provider transport: browser_ui

The initial two attempts exposed a real DeepSeek UI-state defect: upload completed but Enter did not submit an attached-file request. The transport was corrected to clear stale composer attachments, wait for user-visible upload settlement, and click the actual send control for file-bearing turns.
## E2 Embedded Chat user-view proof
Artifact marker: `HWG_EMBEDDED_UI_UPLOAD_E2_T4K7`

Observed from the actual Control Plane Embedded Chat:
- DeepSeek readiness: READY/current.
- ATTACH enabled only because certified media capability is present.
- File chip appeared after canonical upload.
- Send remained enabled.
- Exact marker was returned and rendered visibly in the transcript.
- Browser console errors: 0.
- Screenshot: `.runtime-dev/ui-audit-20260923/chat-upload-e2.png`.

The user-view test also exposed a Markdown bug where intraword underscores were treated as emphasis. The renderer was corrected so identifiers/tokens retain underscores while normal `_italic_` syntax continues to work.

WORK-007 remains PARTIAL because not every media class/provider is E2-certified. WORK-025 remains IN_PROGRESS because the registered human acceptance script is still pending.
