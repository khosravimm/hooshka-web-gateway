# HWG ChatGPT Web Media Qualification ? E1/E2

Date: 2026-09-23
Scope: HWG-WORK-007 / ChatGPT Web provider qualification
Evidence level: E1 + E2

## E1 live discovery
The authenticated ChatGPT Web DOM on the owned shared CDP runtime exposed three file inputs: image/video, image-only, and a generic unrestricted `Attach files` input. The current UI uses `aria-label="Open profile menu"`, composer `aria-label="Ask ChatGPT"`, bare `aria-label="Send"`, and assistant content marked with `data-markdown-text-style="assistant-message"`.

## E2 results
- text / TXT: PASS through the official HWG media qualification endpoint. Hidden marker `HWG_CHATGPT_TXT_E2_V4_H2W9` was returned exactly.
- image / PNG: PASS through the official HWG media qualification endpoint. Marker rendered only inside the image (`HWG_CHATGPT_PNG_E2_V2_M6Q2`) was returned exactly.
- Persisted Provider Profile certification now enables `file_upload`, `document_upload`, and `image_input` for `chatgpt-web`.
- `/v1/capabilities` reflected `files=true`, `vision=true`, `file_upload=true`, `document_upload=true`, and `image_input=true` after certification.

## Drift corrections required for current ChatGPT UI
- Persistent runtime capability object instead of a newly-created capability object per access.
- Current authentication/profile and composer selectors.
- Direct generic `input[type=file]` upload path without requiring the legacy composer-plus button.
- Visual upload lifecycle verification, including provider-renamed attachment filenames.
- Current bare `Send` control.
- Current assistant response surface selector.
- Completion detection based on stable non-transient assistant text while generation is inactive, without requiring the removed copy-action test-id.

## Boundaries
This evidence certifies only the tested text and image representatives for ChatGPT Web. PDF/DOCX/XLSX/PPTX/code/audio/video were not promoted by this record. Provider-side browser success alone was not accepted; the final E2 records were returned through the official HWG qualification endpoint and persisted.
