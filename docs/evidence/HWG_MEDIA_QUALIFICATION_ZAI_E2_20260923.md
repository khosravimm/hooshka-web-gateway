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
- spreadsheet / XLSX: FAIL; response did not contain marker.
- spreadsheet / CSV: NOT CERTIFIED; qualification endpoint timed out (504).
- audio / MP3: not yet E2-tested.
- video / MP4: not yet E2-tested.

Successful qualifications were executed through the official HWG media qualification endpoint and persisted in the Z.ai Provider Profile. No failed/timeout class was promoted to certified.