# Hooshka Web Gateway

Unified Web Chat API gateway for Hooshka. It exposes one governed, OpenAI-compatible local API and routes requests to supported Web-chat providers through provider-specific transports.

> **Canonical product name:** Hooshka Web Gateway
> **Technical id:** `hooshka-web-gateway`
> **Hooshka module id:** `web_gateway`
> **Legacy compatibility id:** `mcp-web-bridge`

## Architecture

This project implements a **Virtual LLM API Gateway** with a **Model Compatibility Proxy (MCP)** layer.

```
Agent Runtime
      |
Virtual LLM API (OpenAI-compatible)
      |
      v
+---------------------+
|      MCP Layer      |  Request Translation / Response Normalization
|  (Compatibility     |
|   Proxy)            |
+---------------------+
      |
      v
+---------------------+
|  Provider Registry  |  Dynamic provider selection
+---------------------+
      |
      v
ChatGPT Web Provider (DOM / Network adapters)
```

### Key Components

- **Provider Interface** (`core/providers.py`): Abstract base class for all LLM providers
- **MCP Layer** (`core/mcp.py`): Request translation, response normalization, session management
- **Provider Registry** (`core/provider_registry.py`): Dynamic provider registration and routing
- **Governance** (`core/governance.py`): Auth, rate limiting, audit logging
- **ChatGPT Web Provider** (`adapters/chatgpt_web_provider.py`): Implements Provider interface with DOM/Network variants

## Status

- MVP-001: PASS
- MVP-002 Gateway: PASS
- Multi-provider architecture: **Foundation complete** (ChatGPT Web provider implemented)

## Endpoints

- `GET /health` - Health check
- `GET /modes` - List available providers and capabilities
- `GET /v1/models` - List available models across providers
- `POST /v1/chat/completions` - OpenAI-compatible chat completions
- `POST /v1/chat/completions` (stream=true) - Streaming responses
- `POST /v1/chat/code` - Code generation with extraction
- `POST /v1/chat/conversation` - Conversation continuity

## Quick Start

```bash
pip install -r requirements.txt
playwright install chromium
python main.py
```

```bash
# Standard chat completion
curl -X POST http://localhost:5000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"messages":[{"role":"user","content":"Reply only with BRIDGE_TEST_OK"}]}'

# Streaming
curl -X POST http://localhost:5000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"messages":[{"role":"user","content":"Count to 10"}],"stream":true}'

# Code generation
curl -X POST http://localhost:5000/v1/chat/code \
  -H "Content-Type: application/json" \
  -d '{"messages":[{"role":"user","content":"Write a Python hello world"}],"language":"python"}'

# Conversation continuity
curl -X POST http://localhost:5000/v1/chat/conversation \
  -H "Content-Type: application/json" \
  -d '{"conversation_id":"my-conv-1","messages":[{"role":"user","content":"Remember: my name is Alice"}]}'
curl -X POST http://localhost:5000/v1/chat/conversation \
  -H "Content-Type: application/json" \
  -d '{"conversation_id":"my-conv-1","messages":[{"role":"user","content":"What is my name?"}]}'
```

## Configuration

Environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `BRIDGE_CDP_URL` | `http://127.0.0.1:9222` | Chrome DevTools Protocol URL |
| `BRIDGE_CHATGPT_URL` | `https://chatgpt.com` | ChatGPT Web URL |
| `BRIDGE_ADAPTER` | `dom` | Adapter: `dom` or `network` |
| `BRIDGE_RATE_LIMIT` | `60` | Default requests per minute |
| `BRIDGE_AUTH_ENABLED` | `false` | Enable API key authentication |

## Provider Adapters

| Adapter | Mode | Streaming | Use Case |
|---------|------|-----------|----------|
| `dom` | DOM-based automation with Playwright selectors | ❌ | Reliable, non-streaming |
| `network` | Network/WebSocket interception via CDP | ✅ | Streaming, faster response |

Set via `BRIDGE_ADAPTER` env var or `provider` field in request.

## Governance

### Authentication
```bash
export BRIDGE_AUTH_ENABLED=true
# Add API keys in GOVERNANCE_CONFIG in main.py
curl -H "Authorization: Bearer YOUR_KEY" ...
```

### Rate Limiting
Default: 60 req/min globally, 20 req/min for ChatGPT Web.
Response headers:
```
X-RateLimit-Limit: 20
X-RateLimit-Remaining: 15
X-RateLimit-Reset: 1699300000
```

### Audit Logging
Structured JSON logs in `logs/audit.log`:
```json
{
  "timestamp": 1699300000.123,
  "request_id": "req_123",
  "event": "request_complete",
  "identity": "user_123",
  "provider": "chatgpt-web",
  "model": "gpt-4",
  "endpoint": "/v1/chat/completions",
  "status_code": 200,
  "latency_ms": 2450,
  "total_tokens": 230
}
```

## Files

Supports single or multiple file uploads through the ChatGPT Web composer. Long texts are chunked automatically.

```bash
curl -X POST http://localhost:5000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"messages":[{"role":"user","content":"Analyze this file"}],"file_paths":["/path/to/file.txt"]}'
```

## Code Generation

`POST /v1/chat/code` extracts code blocks and can return code-only payloads.

```bash
curl -X POST http://localhost:5000/v1/chat/code \
  -H "Content-Type: application/json" \
  -d '{"messages":[{"role":"user","content":"Write a REST API in FastAPI"}],"language":"python","code_only":true}'
```

## Requirements

- Windows
- Chrome running with remote debugging on `http://127.0.0.1:9222`
  ```bash
  chrome.exe --remote-debugging-port=9222 --user-data-dir="C:\chrome-debug"
  ```
- Active ChatGPT session at `https://chatgpt.com`

## Project Structure

```
mcp-web-bridge/
├── main.py                    # Flask app entry point
├── requirements.txt
├── README.md
├── docs/architecture/         # Architecture documentation
│   ├── ADR-001-virtual-llm-gateway.md
│   ├── mcp-definition.md
│   ├── provider-adapter-contract.md
│   └── governance-model.md
├── adapters/
│   ├── chatgpt_dom.py         # Legacy DOM adapter (kept for reference)
│   ├── chatgpt_network.py     # Legacy Network adapter (kept for reference)
│   └── chatgpt_web_provider.py # New Provider interface implementation
├── core/
│   ├── providers.py           # Provider abstract base class
│   ├── mcp.py                 # Model Compatibility Proxy
│   ├── provider_registry.py   # Provider registry & router
│   ├── governance.py          # Auth, rate limiting, audit
│   ├── code_parser.py         # Code block extraction
│   ├── files.py               # File upload handling
│   ├── parser.py              # SSE parsing
│   └── session.py             # Browser session management
├── api/
│   └── openai_compat.py       # Legacy OpenAI-compatible endpoints
└── logs/                      # Runtime logs
```

## Adding New Providers

1. Create adapter in `adapters/<provider_name>.py` implementing `Provider` interface
2. Register in `main.py`:
   ```python
   from adapters.my_provider import MyProvider
   provider_registry.register(MyProvider(config))
   ```
3. Add configuration and rate limits

See `docs/architecture/provider-adapter-contract.md` for full interface specification.

## MCP vs Model Context Protocol

**This project's MCP = Model Compatibility Proxy** (internal translation layer)

**NOT** Model Context Protocol (Anthropic's open standard for LLM-tool integration)

See `docs/architecture/mcp-definition.md` for details.