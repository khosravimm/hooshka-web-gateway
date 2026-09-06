# Web LLM Bridge

Minimal gateway that routes local HTTP requests to the active ChatGPT Web session through Chrome DevTools Protocol.

## Status

- MVP-001: PASS
- MVP-002 Gateway: PASS

## Endpoints

- `GET /health`
- `GET /modes`
- `POST /v1/chat/completions`
- `POST /v1/chat/code`
- `POST /v1/chat/conversation`

## Quick Start

```bash
pip install -r requirements.txt
playwright install chromium
python main.py
```

```bash
curl -X POST http://localhost:5000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"messages":[{"role":"user","content":"Reply only with BRIDGE_TEST_OK"}]}'
```

## Adapters

- `dom` — DOM-based automation with Playwright selectors
- `network` — Network/WebSocket interception via CDP with SSE capture and DOM fallback

## Files

Supports single or multiple file uploads through the ChatGPT Web composer. Long texts are chunked automatically.

## Code Generation

`POST /v1/chat/code` extracts code blocks and can return code-only payloads.

## Requirements

- Windows
- Chrome running with remote debugging on `http://127.0.0.1:9222`
- Active ChatGPT session at `https://chatgpt.com`
