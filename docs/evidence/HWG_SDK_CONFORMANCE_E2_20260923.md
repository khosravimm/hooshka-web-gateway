# HWG SDK Conformance ? E2 ? 2026-09-23

## Scope
Candidate HWG `develop` on `127.0.0.1:5080`; Python and TypeScript reference SDKs.

## Implemented
- Contract discovery: OpenAPI, JSON Schema bundle, Compatibility Manifest.
- Provider/capability/model discovery.
- Explicit provider selection for chat/responses.
- Canonical text/image/file message-part helpers.
- Structured errors preserving HTTP status, code, message, provider and details.
- Existing chat, streaming and Responses API surfaces retained.

## E1 verification
- Python SDK + contract/media targeted suite: PASS.
- TypeScript `tsc --noEmit`: PASS.
- TypeScript contract test: PASS.

## E2 verification
- Candidate runtime health on port 5080: PASS.
- OpenAPI 3.1.0 / HWG contract 1.0.0 fetched through SDK: PASS.
- Unsupported Image Input through Python SDK: HTTP 400 `unsupported_media_type`, provider `deepseek-web`: PASS.
- Python SDK real DeepSeek round-trip returned exact `HWG_SDK_E2_OK`: PASS.
- Unsupported Image Input through TypeScript SDK: HTTP 400 `unsupported_media_type`: PASS.
- TypeScript SDK real DeepSeek round-trip returned exact `HWG_TS_SDK_E2_OK`: PASS.

## Remaining
WORK-009 remains PARTIAL. Profile/account inference targeting and an explicit public cancellation API are not yet complete end-to-end. No image/audio/video provider is certified by this evidence.
