# HWG Explorer Visual Media Recovery — E2

Date: 2026-09-23
Scope: HWG-WORK-007 / Explorer Engine / Z.ai / Qwen
Evidence level: E1 + E2

## User-view discovery correction
Media discovery was extended beyond backend and static DOM signals. Explorer now captures rendered viewport state, screenshot evidence, attachment visibility, upload-busy text, and Send enabled/disabled transitions.

A Z.ai MP4 qualification exposed the concrete failure state in the rendered UI: `Oops! There are files still uploading. Please wait for the upload to complete.` The attachment card existed before the provider considered upload complete, proving that DOM presence alone was insufficient.

Upload readiness now requires a stable non-busy state. If the provider rejects Send because upload is still in progress, the click is not considered committed; the adapter waits and retries within a bounded window.
## Z.ai E2 recovery results
- Spreadsheet / CSV: E2 PASS.
- Spreadsheet / XLSX: E2 PASS; exact cell-A1 marker `HWG_ZAI_XLSX_E2_7395` returned through the official qualification endpoint.
- Video / MP4: provider UI visibly rendered the attached video and returned `HWG_ZAI_VIDEO_E2_5728`; after conversation-scoped visible-assistant fallback was added, the official HWG qualification endpoint also returned the exact marker and persisted `video=true` at E2.
- Audio / MP3: advertised by the live input but not E2-qualified; no existing standards-compliant MP3 encoder was found and no fake artifact was used.

## Explorer robustness
Qwen visual discovery no longer fails the whole run when screenshot capture times out. Screenshot failure is recorded as evidence while other visible state continues. The current Qwen page explicitly displays `Qwen is not available in your region.`; therefore media support remains unqualified rather than being classified unsupported.

Screenshot artifacts remain under `.runtime-dev/discovery-visual/` and are runtime evidence, not source-controlled product data.
