# HWG DeepSeek Target-Provider Self-Use Qualification Evidence

- Evidence ID: `HWG-E2-SELFUSE-DEEPSEEK-20260921-001`
- Date: 2026-09-21
- Product: `HWG 1.0.0-dev.5`
- Discovery Engine: `2.1.0-dev.1`
- Provider: `deepseek-web`
- Scope: target-provider self-use transport qualification only
- Evidence level: `E2` for this scoped transport gate

## Gate being proven

Target-provider self-use is allowed only when deterministic/non-AI mechanisms have identified and tested:

1. message send path;
2. response receive path;
3. response completion detection;
4. one controlled exact-token round-trip.

User permission alone is not sufficient. A stale or missing transport fingerprint fails closed.
## Live validation

Two independent exact-token round-trips were executed against the current DeepSeek development transport.

Gateway API round-trip:

- HTTP status: `200`
- expected token: `HWG_SELF_USE_D73DEF6B9F0C`
- observed token: `HWG_SELF_USE_D73DEF6B9F0C`
- exact match: `true`

Direct provider-adapter qualification round-trip:

- expected marker prefix: `HWG_SELF_USE_`
- exact string comparison: `PASS`
- qualification allowed: `true`
- runtime qualification record: `.runtime-dev/discovery/self-use-gates/deepseek-web.json`
- transport fingerprint: `bf730db991dc5264c65d19c09b56b7dc8a3a53cdc00aceb17bb7121802af1293`

No CAPTCHA/access-control bypass, account rotation, or rate-limit bypass was attempted.
## AI-assisted self-use validation

After the transport qualification was present and fingerprint-matched, AI-Assisted Discovery was executed using `deepseek-web` as the analysis provider for its own discovery evidence.

The result remained deliberately non-authoritative:

- provider used: `deepseek-web`
- model: `deepseek-web`
- routing policy: `least_loaded`
- target provider avoided: `false`
- self-use transport gate: `qualified=true`
- AI evidence level: `E0`
- AI status: `CANDIDATE`
- deterministic validation still required: `true`

This proves the self-use gate and routing behavior, not final Discovery certification or E3 reliability.

## Deterministic regression evidence

- targeted self-use/AI policy tests: `27 passed`
- full HWG deterministic suite: `299 passed`
- compileall: PASS
- JavaScript syntax: PASS
- git diff check: PASS
