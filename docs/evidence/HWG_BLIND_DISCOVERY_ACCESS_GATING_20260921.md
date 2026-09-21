# HWG Blind Discovery & Access Gating Evidence — 2026-09-21

- Evidence ID: `HWG-EVID-BLIND-DISC-20260921`
- Scope: profile-independent provider discovery, authentication/access classification, and post-discovery comparison
- Product: `1.0.0-dev.5`
- Discovery Engine: `2.1.0-dev.1`
- Evidence level: `E1 + live_read_only`
- Safety: no CAPTCHA bypass, restriction bypass, credential extraction, or destructive browser action

## Blind-run rule

The live run did not read `docs/profiles/*` or prior provider discovery artifacts before identifying the current page/provider, access state, controls, capabilities, and observed backend candidates. Prior knowledge was used only after the blind run for comparison.

## Live provider results

- ChatGPT Web: identified from live host/page; `AUTHENTICATED`; composer/send/file-upload observed; static CDN assets excluded from backend API candidates after false-positive fix.
- DeepSeek Web: identified from live host/page; `AUTHENTICATED`; composer, DeepThink, Search, and current API candidates observed.
- Z.ai Web: identified from live host/page; `AUTHENTICATED`; composer, Send, Model Selector, and current API candidates observed.
- Qwen Web: identified from live host/page; classified `BLOCKED` with `region_restriction` after the page displayed `Qwen is not available in your region.` No bypass was attempted.

## Independent comparison

Existing session APIs were queried only after blind discovery. ChatGPT and DeepSeek independently reported authenticated/composer-ready and matched the blind result. Qwen's legacy session endpoint returned `501 Session status not supported`; the blind engine nevertheless identified the explicit regional block. Z.ai blind discovery observed an authenticated composer; the legacy session endpoint timed out in that comparison window, so no independent session PASS is claimed for Z.ai.

For Z.ai, the blind result was compared after discovery with `docs/profiles/zai-web/discovery.v1.1.json`: `model_selector` and nine currently observable endpoints matched. `/api/v1/chats/new` was not observed because no new-chat action occurred in the blind window; absence in one observation is not treated as proof of removal. A `send` control was newly classified.

## Defects found and corrected

1. Authentication false-positive: challenge/login keywords inside ordinary conversation text could contaminate access classification. Detection now uses structural CAPTCHA/challenge/login surfaces rather than transcript content.
2. Backend false-positive: static assets whose filenames contained terms such as `conversation` were incorrectly treated as API candidates. Static asset extensions are now excluded before endpoint classification.
3. Qwen `UNKNOWN` was investigated instead of guessed; the live page proved a provider regional restriction and is now classified `BLOCKED`.

## State-machine rule

Discovery now separates `WAITING_FOR_LOGIN`, `WAITING_FOR_USER_INTERACTION`, `DIAGNOSTIC_REQUIRED`, and `BLOCKED` from `EXPLORATION_READY`. Exploration cannot start from those gated states. After the external condition changes, the run must re-enter `BASELINE_REQUIRED` and capture a fresh baseline before exploration can continue.

This evidence does not certify general provider reliability or E3 operation.
