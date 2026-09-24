# HWG Discovered Provider Media Qualification — GapGPT E1/E2

Date: 2026-09-24
Scope: HWG-WORK-007 / Explorer future-provider media path
Target: `gapgpt-web` discovered from URL, still disabled

## E1 upload surface
- Live page exposes one `input[type=file]`.
- `multiple=true`.
- `accept=""`; therefore HWG did not infer any supported media class from DOM advertisement.
- All class certification remained fail-closed pending real round trips.

## E2 generic discovered-adapter proof
A fresh TXT artifact contained only marker `HWG_GAPGPT_TEXT_E2_6417`.
The prompt did not contain the marker and asked the provider to read the attached file.
The generic `DiscoveredWebProvider.qualify_media()` path returned the exact marker.
Result: text class E2 PASS and `file_upload` behavior proven for that round trip.
## User-view recovery discovered during qualification
GapGPT displayed a blocking Quasar dialog: `در حال آپلود فایل...` with one `قبول` action.
Explorer captured the dialog visually instead of forcing the Send button.
A generic blocking-dialog observer was added; only a single low-risk upload-context OK/Accept action may be auto-dismissed.
Terms, Login, purchase, delete, or other semantic confirmations remain non-automatic.

## Canonical persistence
Discovered-provider registration now incrementally synchronizes missing projected Provider Profile and Account Instance artifacts into the persistent NG store without overwriting existing evidence.
`gapgpt-web:default` and `gapgpt-web:default-account` are now represented in that store.

## Provider quota boundary
A later official `/panel/api/providers/gapgpt-web/media/qualify` call reached a real provider quota condition: `محدودیت پردازش فایل در بسته‌ی رایگان`.
Explorer classifies this as `quota_limited` and upload qualification now fails fast with `provider_quota_limited`.
The official result persisted as E1 failure; `marker_match=false` and runtime `file_upload=false` remained unchanged.
No retry or bypass was attempted.
