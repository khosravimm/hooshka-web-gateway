# HWG Explorer — Visual AI Assistance E2 — 2026-09-24

## Scope
This evidence covers the operational connection between Explorer User-View screenshots and the governed AI-assisted discovery path.
AI remains secondary to deterministic discovery; all AI findings remain E0/CANDIDATE until independently verified.

## Live target
- Target candidate: `gapgpt-web`
- Analyst provider: `deepseek-web`
- Routing required `chat + vision` capability.
- The target provider was avoided for AI analysis.
- Screenshot source was taken only from the candidate's trusted `.runtime-dev/discovery-visual` evidence path.

## Findings
1. The initial visual-AI attempt failed because DeepSeek rendered an image thumbnail without the filename in page text.
2. Live DOM inspection showed a visible `IMG` preview with `alt=20260924T092301462782Z-onboarding-pass-1.png` and a `blob:` source.
3. `visible_page_state()` was extended to observe visible image previews and use their `alt/aria/title/src` metadata for attachment readiness.
4. After the observer fix, Provider Wizard visual AI returned HTTP 200 with the screenshot attached.

## AI hypothesis safety
- Structured hypotheses use contract version `1.0.0`.
- Safe automatic probes are restricted to `inspect`, `hover`, and `focus`.
- `click` hypotheses are placed in `approval_required_queue`.
- Live GapGPT verification produced four `OBSERVED_E1` inspect results and two `REQUIRES_CONFIRMATION` click results.
- Deterministic observations are attached back to hypotheses, but semantic promotion remains blocked.

## Vision isolation tests
### Semantic vision
A synthetic screenshot contained a large solid red circle on the left and a large solid blue square on the right. No shape names were provided in deterministic evidence.
DeepSeek correctly reported both shapes and colors. Result: semantic visual path PASS for this E2 execution window.

### Exact OCR limitation
A separate synthetic screenshot contained the marker `HWG_VISUAL_AI_E2_359719`.
The analyst returned `HW G_VISUAL_AI_E2_359719`, inserting whitespace inside `HWG`.
Result: exact OCR is **not certified** and must not be treated as authoritative evidence. Exact text should prefer DOM/accessibility/deterministic evidence.

## Evidence level
The transport and live visual-analysis path are E2 in this execution window. AI conclusions themselves remain E0/CANDIDATE by policy. No E3 reliability claim is made.
