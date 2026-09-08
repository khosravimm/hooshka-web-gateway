# Governance Model

Centralized governance layer for the Virtual LLM API Gateway.

## Architecture Position

```
Request → [Auth] → [Rate Limit] → [MCP] → [Provider] → [Audit] → Response
              │           │                      │
              ▼           ▼                      ▼
         Identity    Quota/Throttle          Compliance Log
```

## Components

### 1. Authentication
**Purpose:** Verify caller identity

| Method | Status | Details |
|--------|--------|---------|
| API Key | Planned | Header: `Authorization: Bearer <key>` |
| JWT | Future | For service-to-service |
| mTLS | Future | For zero-trust networks |

**Implementation:** Middleware extracts credentials, validates against store, attaches `request.identity`

### 2. Authorization
**Purpose:** Control access to providers/models/features

| Policy | Scope | Example |
|--------|-------|---------|
| Provider allowlist | Identity | User A → OpenAI only |
| Model allowlist | Identity | User A → gpt-4 only |
| Feature flags | Identity | User A → streaming enabled |
| Quota tier | Identity | User A → 1000 req/min |

**Implementation:** Policy engine evaluates `identity + request → allow/deny`

### 3. Rate Limiting
**Purpose:** Protect providers, ensure fair usage

| Algorithm | Use Case |
|-----------|----------|
| Token Bucket | Per-identity burst control |
| Sliding Window | Per-provider smooth limiting |
| Adaptive | Backpressure from provider errors |

**Dimensions:**
- Per identity (API key)
- Per provider (global)
- Per model
- Per conversation (prevent spam)

**Response Headers:**
```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1699300000
Retry-After: 30 (on 429)
```

### 4. Logging & Audit Trail
**Purpose:** Compliance, debugging, billing

**Structured Log Fields:**
```json
{
  "timestamp": "2026-09-07T10:00:00Z",
  "request_id": "req_abc123",
  "identity": "user_123",
  "provider": "chatgpt_web",
  "model": "gpt-4",
  "conversation_id": "conv_xyz",
  "endpoint": "/v1/chat/completions",
  "stream": false,
  "prompt_tokens": 150,
  "completion_tokens": 80,
  "total_tokens": 230,
  "latency_ms": 2450,
  "status": "success",
  "error_code": null,
  "governance": {
    "auth_check_ms": 2,
    "rate_limit_check_ms": 1,
    "policy_decision": "allow"
  }
}
```

**Audit Events (immutable):**
- Authentication success/failure
- Authorization decisions
- Rate limit exceeded
- Provider errors
- Policy violations
- Admin actions (config changes)

### 5. Policy Enforcement
**Purpose:** Organizational rules

| Policy Type | Example |
|-------------|---------|
| Data residency | EU users → EU providers only |
| Cost control | Max $0.01 per request |
| Content filter | Block PII in prompts |
| Model approval | Only approved models |

**Implementation:** OPA (Open Policy Agent) or custom rule engine

## Configuration

```yaml
governance:
  auth:
    enabled: true
    api_keys_file: "config/api_keys.yaml"
    jwt:
      enabled: false
  
  rate_limiting:
    enabled: true
    default_limits:
      requests_per_minute: 60
      tokens_per_minute: 50000
    per_provider:
      chatgpt_web:
        requests_per_minute: 20  # Browser automation is slow
      openai_api:
        requests_per_minute: 300
  
  audit:
    enabled: true
    output: "logs/audit.log"
    format: "json"
    retention_days: 90
  
  policies:
    enabled: false
    engine: "opa"
    bundle_path: "policies/"
```

## Middleware Stack (Request Flow)

```python
# In main.py or gateway.py
app = Flask(__name__)

# 1. Request ID generation
app.before_request(generate_request_id)

# 2. Authentication
app.before_request(auth_middleware)

# 3. Authorization
app.before_request(authorization_middleware)

# 4. Rate Limiting
app.before_request(rate_limit_middleware)

# 5. Request validation / MCP translation
app.before_request(mcp_request_translator)

# 6. Provider routing & execution
app.route("/v1/chat/completions")(chat_completion_handler)

# 7. Response normalization (MCP)
app.after_request(mcp_response_normalizer)

# 8. Audit logging
app.after_request(audit_middleware)

# 9. Rate limit headers
app.after_request(rate_limit_headers_middleware)
```

## Future Extensibility

- **Plugin system** for custom governance modules
- **Webhooks** for real-time event streaming
- **Metrics export** (Prometheus/OpenTelemetry)
- **Dashboard** for monitoring and admin