# HWG Media Qualification ? DeepSeek E2 ? 2026-09-23

## Scope
- Generic media/file qualification framework for all current and future HWG providers.
- DeepSeek Web used as the first pilot provider.
- Candidate runtime: `http://127.0.0.1:5080`, browser CDP `9330`.

## Generic policy
- Qualification is mandatory for all current and future providers.
- Advertised UI/file-picker support is E1 only and never promotes a capability by itself.
- `certified` requires a real E2 provider round-trip.
- Representative classes: text, document, spreadsheet, image, code, presentation, audio, video.

## DeepSeek advertised surface (E1)
- Live DOM exposed `input[type=file]` with `multiple=true`.
- 979 advertised extensions were observed.
- Observed classes: text, document, spreadsheet, image, code, presentation.
- Audio/video representative extensions were not advertised by the current DeepSeek file input.

## DeepSeek E2 qualification
### TXT
- Test file contained marker `HWG_DEEPSEEK_FILE_E2_7K9P` unknown to the prompt.
- HWG qualification endpoint attached the file through the live DeepSeek Web file input.
- DeepSeek returned exactly `HWG_DEEPSEEK_FILE_E2_7K9P`.
- Result: file upload E2 PASS.

### PNG
- Generated PNG contained visible marker `HWG_DEEPSEEK_IMAGE_E2_4M2Q` unknown to the prompt.
- DeepSeek returned exactly `HWG_DEEPSEEK_IMAGE_E2_4M2Q`.
- Result: image input E2 PASS.

## Consumer path E2
Normal Python SDK requests were then sent through `SDK -> HWG -> DeepSeek Web` using `file_paths`:
- TXT marker `HWG_SDK_FILEPATH_E2_R8V3`: PASS.
- PNG marker `HWG_SDK_IMAGEPATH_E2_N6T4`: PASS.

## Runtime promotion
After E2 persistence and restart, DeepSeek runtime capabilities became:
- `files=true`
- `vision=true`
- `file_upload=true`
- `document_upload=true`
- `image_input=true`

Unqualified media remain false. No claim is made for PDF/DOCX/XLSX/PPTX/audio/video processing yet.
