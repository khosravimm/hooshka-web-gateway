# Runtime Naming Registry

This registry assigns stable operational names to Web-chat runtimes used by **Hooshka Web Gateway** (`hooshka-web-gateway`).

## Naming rules

- Prefix all bridge-owned browser/process/runtime artifacts with `MWB-`.
- Use provider-canonical names in lowercase for API ids and kebab-case for file paths.
- Use human-readable labels in evidence and logs.
- A Chrome window/profile without an `MWB-*` runtime name must not be treated as bridge-owned.
- Browser runtimes must be stopped by matching the dedicated profile path, not by matching a website URL alone.

## Provider names

| Canonical provider id | Runtime label | Browser profile / connection | Status label |
|---|---|---|---|
| `chatgpt-web` | `MWB-ChatGPT-Web-CDP` | existing user Chrome CDP, not bridge-owned | `operational-e2` |
| `qwen-web` | `MWB-Qwen-Web-Controller` | `.runtime\\qwen-profile` | `operational-e2` |
| `zai-web` | `MWB-Zai-Web-SSE-Capture` | `.runtime\\zai-profile` or legacy `.runtime\\zai-cdp-profile` | `operational-e2-basic-chat` |
| `deepseek-web` | `MWB-DeepSeek-Web-Frozen` | none while current account is suspended/muted | `blocked-account-state` |

## CDP ports

| Port | Runtime label | Ownership |
|---|---|---|
| `9222` | non-bridge/legacy CDP unless explicitly configured | not assumed bridge-owned |
| `9223` | `MWB-Zai-Web-SSE-Capture` | bridge-owned only when profile path matches `.runtime\\zai-profile` or `.runtime\\zai-cdp-profile` |

## Test labels

| Label | Meaning |
|---|---|
| `MWB-ZAI-MODELS-E2` | Z.ai model discovery through the unified service |
| `MWB-ZAI-NONSTREAM-E2` | Z.ai non-stream chat completion through `/v1/chat/completions` |
| `MWB-ZAI-STREAM-E2` | Z.ai stream-compatible response through `/v1/chat/completions` |
| `MWB-QWEN-NONSTREAM-E2` | Qwen non-stream chat completion through `/v1/chat/completions` |
| `MWB-QWEN-STREAM-E2` | Qwen stream-compatible response through `/v1/chat/completions` |
| `MWB-DEEPSEEK-ACCOUNT-BLOCK` | DeepSeek current account-state circuit breaker |

## Operator rule

If the user reports unexpected provider windows, immediately run an ownership check and stop only bridge-owned runtimes identified by the profile path. Do not close the user's ordinary Chrome tabs by URL alone.
