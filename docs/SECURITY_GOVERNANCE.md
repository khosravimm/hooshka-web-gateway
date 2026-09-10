# Hooshka Web Gateway â€” Security and Governance

## Security objective

The gateway reduces direct coupling to consumer Web-chat interfaces, but it does not convert those services into approved enterprise data processors. Security controls must cover both the local gateway and the upstream Web accounts.

## Trust boundaries

1. Hooshka/client -> local gateway API.
2. Gateway process -> browser/CDP runtime.
3. Browser runtime -> provider Web origin.
4. Provider Web session -> provider backend.
5. Logs/evidence -> local filesystem/Git.

## Mandatory controls

### Loopback-only API

Default bind:

```text
127.0.0.1:5000
```

Do not expose directly to LAN/Internet. Remote access requires a separate reviewed design with authentication, TLS, network ACLs and threat modeling.

### Authentication

Gateway bearer authentication remains enabled. Runtime credentials must not be committed.

### Secret handling

Sensitive artifacts include:

- gateway API key;
- provider cookies/tokens;
- browser profile contents;
- session/local-storage state;
- authorization headers;
- CAPTCHA/proof material.

Never record their values in Git, documentation, screenshots, issue bodies, prompts, or diagnostic output intended for sharing.

### Browser profiles

A provider profile is a security boundary and has one runtime owner at a time. Cleanup must target owned profile paths, never all Chrome instances.

### Exact routing

No silent cross-provider fallback. This prevents accidental data disclosure to an unintended provider.

### Capability fail-closed

Unsupported tools/search/files/vision requests must fail instead of being approximated or routed elsewhere.

### Anti-abuse controls

Never automate CAPTCHA solving, WAF bypass, account/IP rotation, or suspension evasion. Provider-owned normal challenge flows can be completed by the user when required.

## Data governance

Unofficial Web-chat transports are not automatically approved for organizational data.

For SUMS or other organizational workloads, do not submit sensitive, regulated, confidential, patient, employee, infrastructure-secret or security-sensitive data through these providers without a separate approved data-governance decision.

Development/testing should use synthetic/non-sensitive prompts.

## Logging

Default evidence should favor metadata:

- timestamp
- request id
- provider/model
- lifecycle state
- latency
- status/error class
- transport provenance

Avoid raw prompts, reasoning, credentials, tool arguments/results and browser storage.

## Rate/risk control

Provider-specific local rate limits are defense-in-depth, not permission to generate traffic up to the limit.

For Web accounts:

- concurrency 1 by default;
- avoid bursts;
- stop on abnormal-account signals;
- use bounded retries before commitment only;
- no load/stress test.

## Incident classes

- credential exposure
- provider account restriction
- repeated CAPTCHA/challenge
- browser-profile corruption
- unexpected cross-provider routing
- secret in Git/log
- duplicated upstream request due retry
- unauthorized network exposure

Each incident should be recorded with evidence, scope, remediation, rollback and prevention lesson.
