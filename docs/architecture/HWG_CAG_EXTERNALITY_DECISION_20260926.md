# HWG CAG Externality Decision

Date: 2026-09-26
Status: **ACCEPTED / CANONICAL**

## Decision

CAG is external to Hooshka Web Gateway. HWG is a provider/API/agent transport and execution gateway; it must not embed, call, infer, or emulate CAG.

The normal OpenAI-compatible request/response path is transparent with respect to CAG. HWG must not inject CAG system prompts, rewrite model output because it contains commands/code, create CAG action candidates, or contact a CAG endpoint.

If a client application uses CAG, that client owns the CAG workflow. A caller may translate its own external decision into HWG's generic authorization inputs (for example policy or explicit approval) without HWG knowing that CAG exists.

## Runtime consequences

- `core/agent_boundary.py` and the Gateway-to-CAG Action Candidate bridge are removed from active runtime.
- Request translation no longer injects Hooshka/CAG context.
- Response normalization and streaming no longer hide executable text or replace it with Action Plan/CAG messages.
- Tool authorization modes are generic: `none`, `policy`, `approval`.
- No `cag_*` fields exist in HWG's authorization context.
- Historical 0.7.20/0.7.21 documents are retained only as superseded evidence.

## Boundary of responsibility

HWG remains responsible for its own authentication, rate limits, tool descriptors, risk classification, scoped authorization, auditability, provider/account isolation, retry/commitment safety and evidence. These are HWG controls, not CAG integration.
