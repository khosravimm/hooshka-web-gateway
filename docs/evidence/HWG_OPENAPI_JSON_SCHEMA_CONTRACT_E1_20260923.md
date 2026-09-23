# HWG OpenAPI + JSON Schema Contract ? E1 Evidence

Date: 2026-09-23
Work item: HWG-WORK-008
Evidence level: E1

## Implemented
- OpenAPI 3.1 contract generated from the live Flask route registry.
- Machine-readable endpoints: `/v1/contracts/openapi.json`, `/v1/contracts/schemas`, `/v1/compatibility`.
- JSON Schema coverage: ProviderProfile, AccountInstance, Capabilities, Error, Event, CompatibilityManifest.
- Compatibility classification values: native, normalized, reconstructed, emulated, unsupported, uncertified.
- Contract explicitly keeps uncertified multimodal/files features uncertified.

## Verification
- Targeted contract/API tests: 12 passed.
- JSON Schemas validate against Draft 2020-12 meta-schema.
- OpenAPI coverage test asserts agent and management paths are present.

## Scope
This is deterministic E1 contract evidence. No provider capability is promoted by this work.
