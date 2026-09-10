# Runtime Naming Registry

This registry assigns stable operational names to Web-chat runtimes used by **Hooshka Web Gateway** (`hooshka-web-gateway`).

## Naming rules

- Prefix all bridge-owned browser/process/runtime artifacts with `HWG-`.
- Use provider-canonical names in lowercase for API ids and kebab-case for file paths.
- Use human-readable labels in evidence and logs.
- A Chrome window/profile without an `HWG-*` runtime name must not be treated as bridge-owned.
- Browser runtimes must be stopped by matching the dedicated profile path, not by matching a website URL alone.

## Provider names

| Canonical provider id | Runtime label | Browser profile / connection | Status label |
|---|---|---|---|
| `chatgpt-web` | `HWG-ChatGPT-Web-CDP` | `.runtime\\chatgpt-profile`, CDP port `9224` | `operational-e2-kilo` |
| `qwen-web` | `HWG-Qwen-Web-Controller` | `.runtime\\qwen-profile` | `blocked-auth-required` |
| `zai-web` | `HWG-Zai-Web-SSE-Capture` | `.runtime\\zai-profile` or legacy `.runtime\\zai-cdp-profile`, CDP port `9223` | `operational-e2-kilo-text` |
| `deepseek-web` | `HWG-DeepSeek-Web-Frozen` | none while current account is suspended/muted | `blocked-account-state` |

## CDP ports

| Port | Runtime label | Ownership |
|---|---|---|
| `9222` | non-bridge/legacy CDP | not assumed bridge-owned |
| `9223` | `HWG-Zai-Web-SSE-Capture` | bridge-owned only when profile path matches `.runtime\\zai-profile` or `.runtime\\zai-cdp-profile` |
| `9224` | `HWG-ChatGPT-Web-CDP` | bridge-owned only when profile path matches `.runtime\\chatgpt-profile` |

## Test labels

| Label | Meaning |
|---|---|
| `HWG-ZAI-MODELS-E2` | Z.ai model discovery through the unified service |
| `HWG-ZAI-NONSTREAM-E2` | Z.ai non-stream chat completion through `/v1/chat/completions` |
| `HWG-ZAI-STREAM-E2` | Z.ai stream-compatible response through `/v1/chat/completions` |
| `KILO_HWG_CHATGPT_OK` | Kilo CLI `code` agent through `hooshka/chatgpt-web`; large agent prompt path |
| `KILO_HWG_ZAI_GLM53_OK` | Kilo CLI `summary` agent through `hooshka/zai:glm-5.3`; text-only capability path |
| `HWG-QWEN-NONSTREAM-E2` | Qwen non-stream chat completion through `/v1/chat/completions` |
| `HWG-QWEN-STREAM-E2` | Qwen stream-compatible response through `/v1/chat/completions` |
| `HWG-DEEPSEEK-ACCOUNT-BLOCK` | DeepSeek current account-state circuit breaker |

## Operator rule

If the user reports unexpected provider windows, immediately run an ownership check and stop only bridge-owned runtimes identified by the profile path. Do not close the user's ordinary Chrome tabs by URL alone.
