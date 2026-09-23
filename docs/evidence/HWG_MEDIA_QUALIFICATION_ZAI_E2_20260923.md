# HWG Z.ai Media Qualification — E1/E2

Date: 2026-09-23
Scope: HWG-WORK-007 / Z.ai provider qualification

## E1 advertised surface
Live Z.ai DOM exposes one multiple file input. Advertised extensions include PDF, DOC/DOCX, XLS/XLSX, PPT/PPTX, PNG/JPG/SVG, CSV, PY, TXT/MD, MP3 and MP4. Therefore all eight qualification classes are advertised: text, document, spreadsheet, image, code, presentation, audio and video.

## E2 results
- text / TXT: PASS; hidden marker returned.
- image / PNG: PASS; marker rendered only inside image and returned.
- document / PDF: PASS.
- presentation / PPTX: PASS.
- code / PY: PASS.
- spreadsheet / XLSX: E2 PASS after Explorer-assisted UI submission correction; exact A1 marker returned.
- spreadsheet / CSV: E2 PASS; exact hidden marker returned.
- audio / MP3: not yet E2-tested.
- video / MP4: E2 PASS after user-visible upload-state and response-reconstruction corrections; exact marker returned through the official endpoint.

Successful qualifications were executed through the official HWG media qualification endpoint and persisted in the Z.ai Provider Profile. No failed/timeout class was promoted to certified.

## Follow-up qualification ? spreadsheet and video
- CSV v2: E2 PASS; spreadsheet class certified.
- XLSX v2: E2 PASS; exact marker `HWG_ZAI_XLSX_E2_7395` returned through the official HWG qualification endpoint.
- MP4: E2 PASS; exact marker `HWG_ZAI_VIDEO_E2_5728` returned through the official HWG qualification endpoint after upload readiness and visible-assistant fallback were corrected.
- Audio: `.mp3` remains E1 advertised / E2 unqualified because no standards-compliant MP3 test artifact could be produced from existing local tools without installing a new encoder.

Explorer Engine 1.1.0 supplied the user-visible evidence used to diagnose these failures. Historical timeout/failure records remain in Provider Profile history and were never promoted.
