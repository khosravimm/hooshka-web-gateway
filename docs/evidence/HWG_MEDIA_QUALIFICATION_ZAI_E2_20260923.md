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

## Follow-up qualification ? spreadsheet and video
- CSV v2: E2 PASS; exact hidden marker `HWG_ZAI_CSV_E2_A1B2` returned. This promotes the spreadsheet class to certified.
- XLSX v2: FAIL; provider returned incomplete text `HWG_ZAL_` instead of `HWG_ZAI_XLSX_E2_C3D4`. XLSX remains individually uncertified even though the spreadsheet class has a successful CSV representative.
- MP4: upload was observed successfully by Explorer; the user-visible card showed `hwg_zai_video_e2.mp4`, `MP4`, `20.3 KB`, Send was enabled, and `/api/v1/files/` appeared in runtime drift. The qualification request timed out after 150 seconds without a verified marker response, so video remains uncertified.
- Audio: `.mp3` is advertised by the live file input, but no valid MP3 E2 artifact was produced in this slice; audio remains E1/unverified.

Explorer Engine 1.1.0 was used for the follow-up diagnosis rather than external DOM-only scripts. No timeout/failure was promoted to E2.
