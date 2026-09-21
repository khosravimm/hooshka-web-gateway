# HWG Single-Window Origin Isolation — E2 Evidence

- Date: 2026-09-22
- Scope: `HWG-WORK-002`, NG-BRW-001/002/003, ADR-002, ADR-003
- Application line: `1.0.0-dev.6`
- Evidence class: E1 + scoped E2

## Decision under test

The visible UX requirement is one Browser Window with Provider tabs. Storage/session isolation is evaluated at the browser Origin boundary, not merely by Browser Profile path.

For different Provider origins, one shared Chrome Profile may be used while preserving native per-origin cookie/storage isolation. Same-origin multi-account use inside one Chrome Profile is not treated as isolated and requires a separate Profile/Runtime exception.

## Persistent inventory reconciliation

The existing persistent Account Instances were reconciled without replacing their Session metadata. ChatGPT, DeepSeek and Z.ai retained `AUTHENTICATED` session state; Qwen retained `BLOCKED`.
After reconciliation the live NG inventory reported zero isolation conflicts:

- ChatGPT: origin `https://chatgpt.com`, sharing mode `cross_origin_isolated`
- DeepSeek: origin `https://chat.deepseek.com`, sharing mode `cross_origin_isolated`
- Z.ai: origin `https://chat.z.ai`, sharing mode `cross_origin_isolated`
- Qwen: origin `https://chat.qwen.ai`, sharing mode `exclusive_profile`

The running shared Browser/CDP topology itself was not changed by reconciliation; 9330/shared-profile remains the rollback-preserving current runtime path.

## Browser prototype

A temporary Chrome profile, unrelated to HWG authenticated profiles, was launched with one Browser Context and three pages. Two different Origins were represented by `localhost` and `127.0.0.1`; a second `localhost` tab represented same-origin sharing.

Origin A received LocalStorage `A` and cookie `acct=A`. The different Origin could not observe either value. A second tab on Origin A immediately observed both values.
Result:

- `different_origin_isolated = true`
- `same_origin_shared = true`

This validates the architectural boundary: cross-origin Provider tabs can share the visible Browser/Profile UX, while same-origin multi-account isolation must not be claimed inside that Profile.

## Governance consequence

Conflict detection is now keyed by `(Browser Profile path + Origin)`. Missing Origin metadata remains conservative and conflicting until reconciled. Same-origin sharing is represented as `same_origin_conflict`; cross-origin profile sharing is represented as `cross_origin_isolated`.

No cookie database was merged and no authenticated Provider session was modified by the browser prototype. This is not an E3 reliability claim.
