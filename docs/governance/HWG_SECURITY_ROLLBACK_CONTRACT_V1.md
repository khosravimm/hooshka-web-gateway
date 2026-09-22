# HWG Security Rollback Contract v1

Status: `NORMATIVE`
Owner Work Item: `HWG-WORK-010`
Operational Proof: `HWG-WORK-014`

## Purpose
Security completion must define what a rollback is allowed to restore and what it must never silently destroy. This document defines that contract; it does not claim that production cutover/rollback has already been proven.

## Security-sensitive rollback set
A release rollback must restore or verify the application/version manifest, canonical configuration, Provider/Profile/Account relationship metadata, security policy configuration, API-key hash references, schema/contract versions, and release evidence pointers.

Browser profile/session data is mutable runtime state and must not be replaced, copied, merged, or deleted by a code rollback unless a separately approved migration explicitly owns that state.

## Fail-closed rules
- Never restore plaintext secrets from a release artifact.
- Never weaken auth, rate limiting, audit, remote-access or input-validation policy during rollback.
- Refuse destructive rollback when a hash-bound migrated artifact has changed since its recorded rollback point.
- Preserve Account/Profile isolation semantics and Browser Runtime ownership.
- Preserve audit/evidence records; rollback may add a new record but must not erase prior evidence.
- A rollback target must identify its commit/version and configuration hash before execution.

## Required evidence for WORK-014
The controlled cutover/rollback proof must record:

- source commit/version and target rollback commit/version;
- pre-cutover configuration hash and rollback configuration hash;
- health/readiness before cutover, after cutover and after rollback;
- preservation of Account/Profile metadata and mutable browser-profile boundaries;
- security gate state before and after rollback;
- an explicit failure trigger that causes rollback;
- post-rollback verification with no silent downgrade of security policy.

`HWG-WORK-010` may close when this contract is enforced and all other security gates pass. Actual rollback execution and proof remain exclusively owned by `HWG-WORK-014`.
