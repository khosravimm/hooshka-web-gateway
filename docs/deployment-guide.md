# Deployment Guide

## Prerequisites

### System Requirements
- **OS**: Windows 10/11 (primary), Linux/macOS (with Chrome)
- **Python**: 3.10+
- **Chrome/Chromium**: Latest stable
- **Memory**: 4GB+ RAM (8GB recommended)
- **Disk**: 2GB+ free space

### Chrome Setup

1. **Create Chrome profile for debugging**:
   ```cmd
   mkdir C:\chrome-debug
   ```

2. **Start Chrome with remote debugging**:
   ```cmd
   chrome.exe --remote-debugging-port=9222 --user-data-dir="C:\chrome-debug"
   ```

3. **Verify CDP endpoint**:
   Open http://127.0.0.1:9222/json in browser - should show JSON with tabs

4. **Login to ChatGPT**:
   - In the Chrome instance, go to https://chatgpt.com
   - Complete login (Google/Microsoft/Email)
   - Verify you can send messages manually

## Installation

### 1. Clone and Setup
```cmd
git clone <repo-url>
cd mcp-web-bridge
```

### 2. Install Python Dependencies
```cmd
pip install -r requirements.txt
```

### 3. Install Playwright Chromium
```cmd
playwright install chromium
```

### 4. Verify Installation
```cmd
python -c "from main import app; print('OK')"
```

## Configuration

### config.yaml
Copy and modify `config.yaml`:

```yaml
server:
  host: "0.0.0.0"
  port: 5000
  debug: false

cdp:
  url: "http://127.0.0.1:9222"
  timeout: 30000

chatgpt:
  url: "https://chatgpt.com"
  adapter: "dom"  # or "network" for streaming
  long_text_chunk_size: 2048
  request_timeout: 120

providers:
  - id: "chatgpt-web"
    type: "chatgpt_web"
    enabled: true
    priority: 100
    config:
      cdp_url: "http://127.0.0.1:9222"
      chatgpt_url: "https://chatgpt.com"
      adapter: "dom"
      headless: false
      timeout: 120
      long_text_chunk_size: 2048
    capabilities:
      chat_completion: true
      streaming: false  # true for network adapter
      tools: false
      vision: false
      embeddings: false
      max_context_tokens: 128000
      supported_models:
        - "gpt-4"
        - "gpt-4o"
        - "gpt-3.5-turbo"
        - "chatgpt-web"

governance:
  auth:
    enabled: false
    api_keys: {}
    # Example with keys:
    # api_keys:
    #   "sk-your-secure-key": "user-1"
    #   "sk-another-key": "user-2"

  rate_limiting:
    enabled: true
    default_requests_per_minute: 60
    per_provider:
      chatgpt-web:
        requests_per_minute: 20

  audit:
    enabled: true
    output: "logs/audit.log"
    format: "json"
    retention_days: 90

logging:
  level: "INFO"
  file: "logs/bridge.log"
  format: "%(asctime)s - %(levelname)s - %(message)s"
  max_bytes: 10485760
  backup_count: 5
```

### Environment Variables (Override config.yaml)
| Variable | Default | Description |
|----------|---------|-------------|
| `BRIDGE_CDP_URL` | `http://127.0.0.1:9222` | Chrome CDP endpoint |
| `BRIDGE_CHATGPT_URL` | `https://chatgpt.com` | ChatGPT URL |
| `BRIDGE_ADAPTER` | `dom` | `dom` or `network` |
| `BRIDGE_RATE_LIMIT` | `60` | Default req/min |
| `BRIDGE_AUTH_ENABLED` | `false` | Enable API key auth |

## Running

### Development
```cmd
python main.py
```

### Production (with waitress)
```cmd
pip install waitress
waitress-serve --host=0.0.0.0 --port=5000 main:app
```

### As Windows Service (NSSM)
```cmd
nssm install WebLLMBridge
nssm set WebLLMBridge Application python.exe
nssm set WebLLMBridge AppParameters main.py
nssm set WebLLMBridge AppDirectory D:\Code\mcp-web-bridge
nssm start WebLLMBridge
```

### Docker
```dockerfile
# Dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
RUN playwright install chromium

COPY . .
EXPOSE 5000
CMD ["python", "main.py"]
```

```cmd
docker build -t web-llm-bridge .
docker run -p 5000:5000 -v D:\chrome-debug:/chrome-debug web-llm-bridge
```

## API Documentation

Once running, visit:
- **Swagger UI**: http://localhost:5000/docs/
- **OpenAPI Spec**: http://localhost:5000/apispec.json

## Testing

### Automated Tests
```cmd
# Unit tests
python -m pytest tests/test_core.py -v

# Integration tests (requires running server)
python tests/integration_test.py
```

### Manual API Tests
```cmd
# Health
curl http://localhost:5000/health

# List providers
curl http://localhost:5000/modes

# List models
curl http://localhost:5000/v1/models

# Chat completion
curl -X POST http://localhost:5000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"messages":[{"role":"user","content":"Hello!"}]}'

# Streaming
curl -X POST http://localhost:5000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"messages":[{"role":"user","content":"Count to 5"}],"stream":true}'

# Code generation
curl -X POST http://localhost:5000/v1/chat/code \
  -H "Content-Type: application/json" \
  -d '{"messages":[{"role":"user","content":"Python hello world"}],"language":"python"}'

# Conversation
curl -X POST http://localhost:5000/v1/chat/conversation \
  -H "Content-Type: application/json" \
  -d '{"conversation_id":"test-1","messages":[{"role":"user","content":"Remember: 42"}]}'
```

## Monitoring

### Logs
- **Application**: `logs/bridge.log`
- **Audit**: `logs/audit.log` (JSON lines)

### Key Metrics to Monitor
- Request latency (audit.log: `latency_ms`)
- Error rates (audit.log: `status_code` != 200)
- Token usage (audit.log: `total_tokens`)
- Rate limit hits (audit.log: `event: rate_limit_exceeded`)
- Provider health (health checks)

### Prometheus Metrics (Future)
Add `/metrics` endpoint for Prometheus scraping.

## Troubleshooting

### Chrome Connection Issues

**Problem**: "Browser context not found" or "CDP connection failed"
- Verify Chrome is running with `--remote-debugging-port=9222`
- Check http://127.0.0.1:9222/json returns valid JSON
- Ensure no other Chrome instances using port 9222
- Try: `taskkill /f /im chrome.exe` then restart Chrome

**Problem**: "Page not found" or "chatgpt.com not loaded"
- Ensure ChatGPT tab is open in the debug Chrome
- Try navigating manually in that Chrome window
- Increase `cdp.timeout` in config

### ChatGPT Web Issues

**Problem**: "Send button not found" / "Selector timeout"
- ChatGPT UI changed - selectors may need update
- Check `adapters/chatgpt_web_provider.py` for `INPUT_SELECTOR`, `SEND_SELECTOR`
- Use browser DevTools to find new selectors

**Problem**: "File upload failed"
- Verify file exists and is readable
- Check ChatGPT file upload UI hasn't changed
- Increase `MAX_FILE_UPLOAD_TIMEOUT`

**Problem**: Streaming not working (network adapter)
- Ensure `BRIDGE_ADAPTER=network` is set
- Verify CDP captures network responses
- Check `adapters/chatgpt_web_provider.py` SSE parsing

### Rate Limiting

**Problem**: Too many 429 errors
- Increase `governance.rate_limiting.per_provider.chatgpt-web.requests_per_minute`
- ChatGPT Web automation is slow - keep limit low (10-30)

### Authentication

**Problem**: 401 Unauthorized
- Ensure API key is correct: `Authorization: Bearer <key>`
- Check `config.yaml` has the key in `governance.auth.api_keys`
- Verify `governance.auth.enabled: true`

### Performance

**Problem**: Slow responses (>60s)
- Use `network` adapter for streaming
- Reduce `long_text_chunk_size` for faster first response
- Ensure Chrome isn't throttled (run in foreground)

### Memory Leaks

**Problem**: Memory grows over time
- Restart service periodically
- Check `core/session.py` - browser context reuse
- Playwright contexts should be cleaned up in `provider.close()`

## Adding New Providers

1. Create `adapters/<name>_provider.py` implementing `Provider` interface
2. Add provider config to `config.yaml`
3. Register in `main.py`:
   ```python
   from adapters.my_provider import MyProvider
   provider_registry.register(MyProvider(config))
   ```
4. Add rate limits in config
5. Write tests in `tests/providers/test_<name>.py`

See `docs/architecture/provider-adapter-contract.md` for interface details.

## Security Considerations

1. **Never expose directly to internet** - Use reverse proxy (nginx, Cloudflare)
2. **Enable authentication** in production: `governance.auth.enabled: true`
3. **Use HTTPS** - Terminate TLS at reverse proxy
4. **Restrict CDP access** - Chrome debug port should be localhost only
5. **Audit logs** - Review `logs/audit.log` regularly
6. **API keys** - Rotate periodically, use strong random keys

## Backup & Recovery

- **Config**: Backup `config.yaml`
- **Logs**: Rotate automatically (configured in logging)
- **Sessions**: In-memory, lost on restart (by design)
- **Chrome profile**: `C:\chrome-debug` persists login state

## Upgrading

1. Pull latest changes
2. Update dependencies: `pip install -r requirements.txt`
3. Run tests: `python -m pytest tests/`
4. Restart service

## Support

Check logs first:
```cmd
type logs\bridge.log
type logs\audit.log
```

Common solutions:
- Restart Chrome debug instance
- Restart Python service
- Clear Chrome cache in debug profile
- Verify ChatGPT.com accessible (not blocked)