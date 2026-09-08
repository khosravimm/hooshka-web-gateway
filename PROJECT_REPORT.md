# Web LLM Bridge - Project Report

## Overview

**Name:** Web LLM Bridge
**Type:** Virtual LLM API Gateway with Model Compatibility Proxy (MCP)
**Language:** Python 3.13
**Framework:** Flask + Playwright
**Purpose:** Routes local HTTP requests to ChatGPT Web through Chrome DevTools Protocol

---

## Architecture

```
Agent Runtime
      |
Virtual LLM API (OpenAI-compatible)
      |
      v
+---------------------+
|      MCP Layer      |  core/mcp.py
|  - Translator
|  - Normalizer
|  - Session Manager
+---------------------+
      |
      v
+---------------------+
|  Provider Registry  |  core/provider_registry.py
+---------------------+
      |
      v
ChatGPT Web Provider (DOM/Network adapters)
```

---

## Project Structure

```
D:\Code\mcp-web-bridge\
├── main.py                      # Flask app entry point
├── config.yaml                  # Configuration
├── requirements.txt             # Dependencies
├── README.md
├── manage.py                    # CLI management tool
├── service_manager.ps1          # Windows service manager
├── service_manager.bat          # Batch wrapper
├── control_panel.py             # Web dashboard blueprint
├── adapters/
│   └── chatgpt_web_provider.py  # ChatGPT Web provider (async)
├── core/
│   ├── providers.py             # Provider ABC + dataclasses
│   ├── mcp.py                   # MCP layer
│   ├── provider_registry.py     # Registry & router
│   ├── governance.py            # Auth, rate limit, audit
│   ├── config.py                # YAML config loader
│   ├── code_parser.py           # Code block extraction
│   └── files.py                 # File handling (async)
├── docs/
│   ├── architecture/            # ADR, MCP definition, contracts
│   ├── deployment-guide.md
│   └── troubleshooting.md
├── tests/
│   ├── test_core.py             # Unit tests (31 passing)
│   └── integration_test.py      # Integration test script
├── logs/
│   ├── bridge.log               # Application logs
│   └── audit.log                # JSON audit trail
└── .venv/                       # Python virtual environment
```

---

## What's Working

| Component | Status | Evidence |
|-----------|--------|----------|
| **Provider Interface** | ✅ Works | 31 unit tests pass |
| **MCP Layer** | ✅ Works | Tests pass for translator/normalizer/session |
| **Provider Registry** | ✅ Works | Registration, routing, priority sorting tested |
| **Governance** | ✅ Works | Rate limiter, auth manager tests pass |
| **Config Loading** | ✅ Works | YAML config loads correctly |
| **Flask App** | ✅ Works | Server starts on port 5000 |
| **Swagger API Docs** | ✅ Works | Available at /docs/ |
| **Control Panel** | ✅ Works | Available at /panel/ (chart fixed) |
| **Direct Provider Usage** | ✅ Works | Tested with `DIRECT_TEST_OK` response |
| **Unit Tests** | ✅ 31 pass | `python -m pytest tests/test_core.py -v` |

---

## Known Problems

### Problem 1: Playwright Async API in Flask Context (CRITICAL)

**Symptom:**
- First chat completion request works
- All subsequent requests fail with: `Page.wait_for_selector: 'NoneType' object has no attribute 'send'`

**Root Cause:**
Playwright's async API has WebSocket connection instability when used in Flask's request handling context. The connection to Chrome DevTools Protocol (CDP) breaks after the first operation.

**Evidence:**
```bash
# Test 1 (works):
POST /v1/chat/completions → "BRIDGE_TEST_OK" ✅

# Test 2 (fails):
POST /v1/chat/completions → "Page.wait_for_selector: 'NoneType' object has no attribute 'send'" ❌

# Direct Python test (always works):
asyncio.run(provider.chat_completion(request)) → "DIRECT_TEST_OK" ✅
```

**Workaround:**
Use the provider directly in Python scripts, not through Flask API.

**Permanent Fix Needed:**
Refactor to use one of:
1. Queue-based architecture (requests processed in separate event loop)
2. Subprocess per request (each request spawns new process)
3. HTTP-based automation instead of browser automation

---

### Problem 2: Legacy Modules Conflict (RESOLVED)

**Original Symptom:**
"It looks like you are using Playwright Sync API inside the asyncio loop"

**Root Cause:**
Legacy modules (`core/session.py`, `adapters/chatgpt_dom.py`, `adapters/chatgpt_network.py`, `api/openai_compat.py`) imported `sync_playwright` at module level, which initialized Playwright's sync API global state and conflicted with the async API.

**Resolution:**
Backed up legacy modules with `.bak` extension. Only async API is now used.

**Files Modified:**
- `adapters/chatgpt_dom.py` → `adapters/chatgpt_dom.py.bak`
- `adapters/chatgpt_network.py` → `adapters/chatgpt_network.py.bak`
- `core/session.py` → `core/session.py.bak`
- `api/openai_compat.py` → `api/openai_compat.py.bak`

---

### Problem 3: Windows Service Cannot Access Chrome (BY DESIGN)

**Symptom:**
Windows service installed but fails to start or cannot connect to Chrome CDP.

**Root Cause:**
Windows services run in session 0 (LocalSystem), but Chrome debug instance runs in user's session. They cannot communicate.

**Resolution:**
Use one of:
- Run directly: `python main.py`
- Scheduled Task at user logon
- NSSM with interactive service

---

## Testing Instructions

### Prerequisites

1. **Python 3.10+** with virtual environment at `.venv/`
2. **Chrome** installed at `C:\Program Files\Google\Chrome\Application\chrome.exe`
3. **Active ChatGPT session** (manually logged in)

### Setup

```powershell
# 1. Create venv and install dependencies
cd D:\Code\mcp-web-bridge
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt

# 2. Start Chrome with remote debugging
Start-Process "C:\Program Files\Google\Chrome\Application\chrome.exe" -ArgumentList "--remote-debugging-port=9222", "--user-data-dir=C:\chrome-debug"
# → Open https://chatgpt.com in that Chrome window
# → Login to ChatGPT

# 3. Start the server
.venv\Scripts\python.exe main.py
```

### Test 1: Unit Tests (Always Works)
```bash
.venv\Scripts\python.exe -m pytest tests/test_core.py -v
# Expected: 31 passed
```

### Test 2: Health Endpoints
```bash
curl http://localhost:5000/health
# Expected: {"status": "ok"}

curl http://localhost:5000/modes
# Expected: JSON with providers list

curl http://localhost:5000/v1/models
# Expected: JSON with models list
```

### Test 3: Direct Provider Usage (WORKS)
```powershell
.venv\Scripts\python.exe -c "
import asyncio
from adapters.chatgpt_web_provider import create_chatgpt_web_provider
from core.providers import ChatCompletionRequest

async def test():
    provider = create_chatgpt_web_provider()
    request = ChatCompletionRequest(
        model='chatgpt-web',
        messages=[{'role': 'user', 'content': 'Reply only with TEST_OK'}]
    )
    response = await provider.chat_completion(request)
    print(response.choices[0].message.content)
    await provider.close()

asyncio.run(test())
"
# Expected: TEST_OK
```

### Test 4: Flask API (PARTIAL - First request only)
```bash
# First request (works):
curl -X POST http://localhost:5000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"messages":[{"role":"user","content":"Say hi"}]}'
# Expected: {"choices":[{"message":{"content":"Hi!..."}}]}

# Second request (fails with Playwright error)
# Need to restart server between requests
```

### Test 5: Control Panel
```
Open browser: http://localhost:5000/panel/
- Overview tab: Stats cards, chart (fixed height)
- Providers tab: List of registered providers
- Sessions tab: Active conversations
- Logs tab: View bridge.log, audit.log
- Config tab: View config.yaml
```

### Test 6: Swagger API Docs
```
Open browser: http://localhost:5000/docs/
- Interactive API documentation
- All endpoints documented
```

---

## Dependencies (requirements.txt)

```
flask>=2.3.0
playwright>=1.40.0
flasgger>=0.9.7
pyyaml>=6.0
pytest>=7.0
pytest-asyncio>=0.21
psutil>=5.9
requests (installed separately)
```

---

## Configuration (config.yaml)

Key settings:
- `server.port: 5000`
- `cdp.url: http://127.0.0.1:9222`
- `chatgpt.adapter: network` (changed from "dom" for streaming)
- `governance.rate_limiting.per_provider.chatgpt-web.requests_per_minute: 20`

---

## Key API Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| GET | /health | Health check |
| GET | /modes | List providers |
| GET | /v1/models | List models |
| POST | /v1/chat/completions | Chat completion |
| POST | /v1/chat/completions (stream=true) | Streaming |
| POST | /v1/chat/code | Code generation |
| POST | /v1/chat/conversation | Conversation continuity |
| GET | /panel/ | Control panel |
| GET | /docs/ | Swagger API docs |

---

## Architecture Documentation

Located in `docs/architecture/`:
- `ADR-001-virtual-llm-gateway.md` - Architecture decision record
- `mcp-definition.md` - MCP vs Model Context Protocol clarification
- `provider-adapter-contract.md` - Provider interface spec
- `governance-model.md` - Auth, rate limiting, audit design

---

## Management Tools

### CLI (`manage.py`)
```bash
.venv\Scripts\python.exe manage.py providers list
.venv\Scripts\python.exe manage.py sessions list
.venv\Scripts\python.exe manage.py logs bridge -n 50
.venv\Scripts\python.exe manage.py stats
.venv\Scripts\python.exe manage.py config show
```

### Windows Service (Admin required)
```powershell
.\service_manager.ps1 install
.\service_manager.ps1 start
.\service_manager.ps1 status
```

---

## Recommended Testing Approach for Another Agent

1. **Start with unit tests** to verify core architecture works
2. **Test direct provider usage** to verify Playwright + Chrome integration
3. **Test Flask health endpoints** to verify server runs
4. **Test Flask chat endpoint** once (expect success) then again (expect failure)
5. **View control panel** at `/panel/` to verify UI
6. **View Swagger docs** at `/docs/` to verify API documentation

---

## Summary

| Aspect | Status |
|--------|--------|
| Architecture Design | ✅ Complete and well-documented |
| Core Implementation | ✅ All tests pass |
| Direct Usage | ✅ Works perfectly |
| Flask API | ⚠️ First request works, subsequent fail |
| Control Panel | ✅ Works (chart fixed) |
| Documentation | ✅ Comprehensive |
| Ready for Production | ❌ Needs Playwright stability fix |

**Bottom line:** The architecture is solid and the core works. The Flask integration has a Playwright async API issue that needs a refactor (queue-based or subprocess-based) to be production-ready. For now, use direct Python scripts to interact with the provider.