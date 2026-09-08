# Troubleshooting Guide

## Quick Diagnostic Commands

```bash
# Check server health
curl http://localhost:5000/health

# Check providers
curl http://localhost:5000/modes | jq .

# Check models
curl http://localhost:5000/v1/models | jq .

# View recent logs
tail -n 50 logs/bridge.log
tail -n 50 logs/audit.log
```

---

## Common Issues

### 1. Chrome/CDP Connection

| Symptom | Cause | Solution |
|---------|-------|----------|
| `Browser context not found` | No Chrome with CDP running | Start Chrome: `chrome.exe --remote-debugging-port=9222 --user-data-dir="C:\chrome-debug"` |
| `Connection refused: 127.0.0.1:9222` | Wrong port or Chrome not started | Verify port 9222, check firewall |
| `Page not found: chatgpt.com` | No ChatGPT tab in debug Chrome | Open https://chatgpt.com in the debug Chrome window |
| `Timeout waiting for selector` | ChatGPT UI changed | Update selectors in `adapters/chatgpt_web_provider.py` |

**Verify CDP:**
```bash
curl http://127.0.0.1:9222/json
# Should return JSON array of tabs
```

### 2. ChatGPT Web Automation

| Symptom | Cause | Solution |
|---------|-------|----------|
| `Send button not found` | Selector outdated | Inspect ChatGPT DOM, update `SEND_SELECTOR` |
| `Input selector failed` | Textarea selector changed | Update `INPUT_SELECTOR` |
| `File upload timeout` | Large file or UI change | Increase `MAX_FILE_UPLOAD_TIMEOUT`, check file size |
| `Response empty` | Extraction failed | Check `ASSISTANT_SELECTOR`, verify response parsing |
| `Streaming returns empty` | Network adapter not capturing | Verify CDP network monitoring, check SSE parsing |

**Debug Selectors:**
```python
# In Python REPL with running server
from core.session import get_page
page, _, _ = get_page()
page.wait_for_selector("#prompt-textarea", timeout=5000)
print("Input found")
```

### 3. Rate Limiting

| Symptom | Cause | Solution |
|---------|-------|----------|
| `429 Too Many Requests` | Exceeded rate limit | Increase limit in config, add delays between requests |
| `Rate limit too strict` | Default 20/min for ChatGPT | Adjust `governance.rate_limiting.per_provider.chatgpt-web` |

**Check Rate Limit Headers:**
```bash
curl -v http://localhost:5000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"messages":[{"role":"user","content":"test"}]}'
# Look for X-RateLimit-* headers
```

### 4. Authentication

| Symptom | Cause | Solution |
|---------|-------|----------|
| `401 Unauthorized` | Invalid/missing API key | Check `Authorization: Bearer <key>` header |
| `Auth enabled but no keys` | Config missing api_keys | Add keys to `governance.auth.api_keys` in config.yaml |

### 5. Streaming Issues

| Symptom | Cause | Solution |
|---------|-------|----------|
| `Stream returns all at once` | Using DOM adapter with stream=true | Set `BRIDGE_ADAPTER=network` for true streaming |
| `Stream chunks malformed` | SSE parsing error | Check `core/parser.py` for SSE format changes |
| `Connection drops mid-stream` | Timeout | Increase `chatgpt.request_timeout` |

### 6. Conversation/Session

| Symptom | Cause | Solution |
|---------|-------|----------|
| `Conversation not remembered` | Wrong conversation_id | Use same `conversation_id` in subsequent requests |
| `New conversation each request` | Missing conversation_id | Always provide `conversation_id` for continuity |
| `Provider session lost` | Chrome context reset | Session stored in MCP, survives provider restarts |

---

## Log Analysis

### bridge.log (Application Logs)
```bash
# Errors only
grep ERROR logs/bridge.log

# By provider
grep "chatgpt-web" logs/bridge.log

# By endpoint
grep "/v1/chat/completions" logs/bridge.log

# Performance
grep "latency_ms" logs/bridge.log
```

### audit.log (Structured Audit)
```bash
# All events
cat logs/audit.log | jq .

# Failed requests
cat logs/audit.log | jq 'select(.status_code >= 400)'

# By provider
cat logs/audit.log | jq 'select(.provider == "chatgpt-web")'

# Slow requests (>10s)
cat logs/audit.log | jq 'select(.latency_ms > 10000)'

# Rate limit events
cat logs/audit.log | jq 'select(.event == "rate_limit_exceeded")'

# Auth failures
cat logs/audit.log | jq 'select(.event == "auth_failure")'
```

---

## Selector Updates (ChatGPT UI Changes)

When ChatGPT updates their UI, these selectors may need updating in `adapters/chatgpt_web_provider.py`:

```python
# Current selectors (as of 2026)
INPUT_SELECTOR = "#prompt-textarea"
SEND_SELECTOR = "button[data-testid='send-button']"
ASSISTANT_SELECTOR = "[data-message-author-role='assistant']"
FILE_INPUT_SELECTOR = "input[type='file']"
UPLOAD_READY_SELECTOR = "button[data-testid='send-button'], text=Upload complete, .upload-complete"
```

**To find new selectors:**
1. Open ChatGPT in debug Chrome
2. Right-click element → Inspect
3. Copy selector (CSS or XPath)
4. Update in code

---

## Performance Tuning

### Faster Responses
1. **Use network adapter** for streaming: `BRIDGE_ADAPTER=network`
2. **Reduce chunk size**: Lower `long_text_chunk_size` (default 2048)
3. **Disable file uploads** if not needed
4. **Keep Chrome window active** (not minimized)

### Memory Management
- Provider reuses browser context
- Restart service daily for long-running deployments
- Monitor `logs/bridge.log` for memory errors

---

## Debugging Mode

Run with verbose logging:
```bash
# Debug level
$env:BRIDGE_LOG_LEVEL = "DEBUG"
python main.py

# Or in config.yaml:
logging:
  level: "DEBUG"
```

### Interactive Debugging
```python
# Start Python REPL
from core.session import get_page
from adapters.chatgpt_web_provider import create_chatgpt_web_provider

page, pw, browser = get_page()
# Test selectors manually
page.locator("#prompt-textarea").count()
```

---

## Network Adapter Specific

### CDP Network Monitoring
The network adapter intercepts responses via CDP:
```python
page.on("response", on_response)
```

**If streaming fails:**
1. Check CDP captures `/backend-api/f/conversation` responses
2. Verify `Content-Type: text/event-stream`
3. Check SSE parsing in `core/parser.py`

### Common CDP Issues
- **Multiple Chrome instances**: Only first with port 9222 works
- **Chrome updates**: CDP protocol may change
- **Headless mode**: Some features don't work headless

---

## Error Codes Reference

| Code | HTTP | Meaning | Action |
|------|------|---------|--------|
| `invalid_request_error` | 400 | Bad request format | Check request body |
| `authentication_error` | 401 | Invalid API key | Check auth config |
| `rate_limit_error` | 429 | Too many requests | Wait, increase limit |
| `provider_unavailable` | 503 | No healthy provider | Check Chrome, provider health |
| `adapter_error` | 500 | Adapter failure | Check bridge.log |
| `provider_timeout` | 504 | Provider timeout | Increase timeout |
| `internal_error` | 500 | Unexpected error | Check logs |

---

## Getting Help

1. Check logs first: `logs/bridge.log`, `logs/audit.log`
2. Run integration tests: `python tests/integration_test.py`
3. Verify Chrome CDP: `curl http://127.0.0.1:9222/json`
4. Test manually with curl
5. Check GitHub issues for known problems

---

## Reset Procedure

If everything fails:
```cmd
# 1. Kill all Chrome
taskkill /f /im chrome.exe

# 2. Clear Chrome debug profile (optional - loses login)
rmdir /s /q C:\chrome-debug

# 3. Restart Chrome debug
chrome.exe --remote-debugging-port=9222 --user-data-dir="C:\chrome-debug"

# 4. Login to ChatGPT manually

# 5. Restart bridge
python main.py
```