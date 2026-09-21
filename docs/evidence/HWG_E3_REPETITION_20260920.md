# E3 Repetition Evidence — S1 baseline per provider (live, 2026-09-20)

Criterion: 3 consecutive exact-match runs (E3 upgrades E2 → reliability).

## chatgpt-web — E3 PASS (3/3)
14s / 13s / 13s... precisely: 14s, 13s, 14s — all exact `HWG_E2_OK`.

## deepseek-web — E3 PASS (3/3)
12s, 11s, 11s — all exact, no captcha/login/suspension signals.

## zai-web (glm-5.2) — E3 FAIL (1/3)
- run 1: HTTP 500 after 240s (operation timeout, CancelledError, empty message)
- run 2: 200 in 148s, exact
- run 3: HTTP 500 after 240s (same timeout signature)
- Pattern matches earlier observations: zai alternates fast (21–148s) and
  total stalls; server-side congestion/throttle suspected (client rate is
  within the 6 RPM config). Fail-closed in all cases (no fabricated answers).

## Stall root cause — DIAGNOSED (upstream latency, not adapter)
Instrumented runs on the shared browser (submit→poll markers in bridge.log):
- Fast run (15s): backend request seen after **4.2s**, first text after **6.1s**.
- Slow run (162s): backend request seen after **76.1s**, first text after **153.4s**.

The request consistently reaches z.ai; the variance is entirely in the time z.ai's
backend takes to (a) accept the request and (b) stream the first token. Our
transport is fail-closed and correct: it submits reliably and times out cleanly
(no fabricated output). This is upstream congestion/throttle, not a code defect.

## Verdict
- Reliability claim allowed: chatgpt-web S1, deepseek-web S1.
- zai-web stays E2 (single successes only); upstream latency (4–76s to first
  backend acceptance) is the documented cause; no code-side fix available.
