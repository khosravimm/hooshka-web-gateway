# HWG Provider E3 Reliability Program v1

Status: `NORMATIVE`
Work Item: `HWG-WORK-013`
Evidence model: Mission §19 / NG-EVIDENCE-001

## Purpose
E2 proves a real end-to-end success. E3 is a reliability claim and therefore requires repeated evidence across predefined independent windows. A burst of consecutive successes inside one window remains a window result, not full E3.

## Predefined E3 contract
For each exact Provider/Account/Model scope:

- Three independent windows are required: W1, W2, W3.
- Window starts must be at least 30 minutes apart.
- Each window runs three bounded exact-token functional probes.
- A window passes only at 3/3 exact matches.
- Every successful probe must finish with `commitment_state=terminal` and `retry_allowed=false`.
- Any LOGIN_REQUIRED, USER_INTERACTION_REQUIRED, BLOCKED, challenge, account restriction, timeout or mismatched response fails that window.
- No silent provider/model/account substitution is allowed.
- E3 may be claimed only when all three windows pass for the same scope.

Historical same-window repetitions may be retained as baseline evidence but cannot substitute for the three-window contract.
