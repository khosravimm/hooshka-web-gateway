# HWG Multimodal Canonical Contract ? E1 Evidence

- Work item: HWG-WORK-007
- Date: 2026-09-23
- Evidence level: E1
- Release line: 1.0.0-dev.7

## Implemented

HWG now exposes one versioned media contract for text, image input/output, file/document upload, audio input/output, and video input/output. Each media kind publishes support state plus MIME, size, duration/resolution, lifecycle and privacy constraint fields.

The same contract is projected into Provider Profiles and `/v1/capabilities`. Requests containing uncertified media are rejected with `unsupported_media_type` before provider execution. Existing provider capabilities are not upgraded by assumption: no new media capability is marked supported without provider evidence.

## Verification

- Focused media/API/profile tests: 25 passed.
- Full deterministic suite: 434 passed.
- `compileall`: PASS.
- `git diff --check`: PASS.

## Remaining

E2 remains required. At least one provider/media path must be live-qualified with real constraints and Embedded Chat must enable only certified media before HWG-WORK-007 can be marked DONE.
