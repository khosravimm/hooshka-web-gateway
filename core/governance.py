from functools import wraps
from flask import request, jsonify, g, has_request_context
import time
import logging
import json
from typing import Optional, Callable
from collections import defaultdict
from threading import Lock

logger = logging.getLogger(__name__)


class RateLimiter:
    def __init__(self):
        self._buckets: dict[str, dict] = defaultdict(lambda: {"tokens": 0, "last_refill": 0})
        self._lock = Lock()
        self._default_rate = 60
        self._default_burst = 10
        self._provider_rates: dict[str, tuple[int, int]] = {}
        self._enabled = True
    
    def set_rate(self, key: str, requests_per_minute: int, burst: int = None):
        self._provider_rates[key] = (requests_per_minute, burst or requests_per_minute // 6 + 1)
    
    def check_rate_limit(self, identity: str, provider_id: str = "default") -> tuple[bool, dict]:
        rate, burst = self._provider_rates.get(provider_id, (self._default_rate, self._default_burst))
        
        with self._lock:
            bucket = self._buckets[(identity, provider_id)]
            now = time.time()
            
            elapsed = now - bucket["last_refill"]
            refill_amount = elapsed * (rate / 60.0)
            bucket["tokens"] = min(burst, bucket["tokens"] + refill_amount)
            bucket["last_refill"] = now
            
            if bucket["tokens"] >= 1:
                bucket["tokens"] -= 1
                return True, {
                    "limit": rate,
                    "remaining": int(bucket["tokens"]),
                    "reset": int(now + (burst - bucket["tokens"]) * 60 / rate),
                }
            
            return False, {
                "limit": rate,
                "remaining": 0,
                "reset": int(now + (1 - bucket["tokens"]) * 60 / rate),
            }


class AuthManager:
    """Verify-only API-key manager.

    Only ``sha256:`` hashes are kept in memory. Plaintext tokens are hashed
    on the way in (add_key/load_keys) and on verify; secrets never persist.
    """

    def __init__(self):
        self._api_keys: dict[str, dict] = {}
        self._enabled = True

    def load_keys(self, keys: dict[str, dict]):
        from core.key_hash import normalize_ref
        normalized = {}
        for key, value in (keys or {}).items():
            ref = normalize_ref(key)
            if isinstance(value, str):
                normalized[ref] = {"identity": value, "metadata": {}}
            elif isinstance(value, dict):
                normalized[ref] = {
                    "identity": value.get("identity", "anonymous"),
                    "metadata": value.get("metadata", {}),
                }
            else:
                logger.warning("Ignoring invalid auth identity mapping for one API key")
        self._api_keys = normalized

    def add_key(self, key: str, identity: str, metadata: dict = None):
        from core.key_hash import normalize_ref
        self._api_keys[normalize_ref(key)] = {"identity": identity, "metadata": metadata or {}}

    def verify(self, api_key: str) -> Optional[dict]:
        if not self._enabled:
            return {"identity": "anonymous", "metadata": {}}

        from core.key_hash import hash_token
        return self._api_keys.get(hash_token(api_key or ""))
    
    def extract_key(self) -> Optional[str]:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            return auth_header[7:]
        # Credentials in URLs can leak through browser/proxy/server logs.
        return None


_AUDIT_SECRET_TERMS = ("token", "secret", "api_key", "authorization", "cookie", "password")
_AUDIT_CONTENT_KEYS = {"prompt", "messages", "content", "body", "request_body", "response_body", "headers"}
_AUDIT_TELEMETRY_TOKEN_KEYS = {"prompt_tokens", "completion_tokens", "total_tokens"}

def _sanitize_audit_value(value):
    if isinstance(value, dict):
        out = {}
        for key, item in value.items():
            normalized = str(key).lower().replace("-", "_")
            if normalized in _AUDIT_TELEMETRY_TOKEN_KEYS:
                out[key] = _sanitize_audit_value(item)
            elif normalized in _AUDIT_CONTENT_KEYS or any(term in normalized for term in _AUDIT_SECRET_TERMS):
                out[key] = "[REDACTED]"
            else:
                out[key] = _sanitize_audit_value(item)
        return out
    if isinstance(value, list):
        return [_sanitize_audit_value(x) for x in value]
    return value


class AuditLogger:
    def __init__(self, log_file: str = "logs/audit.log"):
        self._log_file = log_file
        self._enabled = True
    
    def log(self, event: dict):
        if not self._enabled:
            return
        
        event = _sanitize_audit_value(dict(event or {}))
        event["timestamp"] = time.time()
        event["request_id"] = getattr(g, "request_id", "unknown") if has_request_context() else "unknown"
        
        try:
            with open(self._log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(event, ensure_ascii=False) + "\n")
        except Exception as e:
            logger.error(f"Audit log write failed: {e}")


rate_limiter = RateLimiter()
auth_manager = AuthManager()
audit_logger = AuditLogger()


def generate_request_id():
    g.request_id = f"req-{int(time.time() * 1000000)}"
    g.start_time = time.time()


def _is_loopback_request():
    return request.remote_addr in ("127.0.0.1", "::1", "localhost")


def auth_middleware():
    if request.path in ("/health", "/ready", "/health/deep") and _is_loopback_request():
        g.identity = {"identity": "health-check", "metadata": {"source": "loopback"}}
        g.api_key = None
        return

    # Localhost is the trusted same-host control plane for Hooshka Console and other callers;
    # and internal provider probes. Do not require a bearer token for true
    # loopback clients, but do not extend this to LAN/private ranges or forwarded
    # headers. request.remote_addr is the socket peer address observed by Flask.
    if _is_loopback_request():
        g.identity = {"identity": "local-loopback", "metadata": {"source": "loopback", "path": request.path}}
        g.api_key = None
        return

    api_key = auth_manager.extract_key()
    identity_info = auth_manager.verify(api_key) if api_key else None
    
    if auth_manager._enabled and not identity_info:
        audit_logger.log({
            "event": "auth_failure",
            "reason": "invalid_api_key",
            "ip": request.remote_addr,
        })
        return jsonify({"error": {"message": "Invalid API key", "type": "authentication_error"}}), 401
    
    g.identity = identity_info or {"identity": "anonymous", "metadata": {}}
    g.api_key = api_key


def rate_limit_middleware():
    if not rate_limiter._enabled:
        return
    if request.path in ("/health", "/ready", "/health/deep") or (request.path.startswith("/panel") and _is_loopback_request()):
        return
    identity_info = g.get("identity") or {}
    identity = identity_info.get("identity", "anonymous")
    provider_id = getattr(g, "selected_provider_id", "default")
    
    allowed, headers = rate_limiter.check_rate_limit(identity, provider_id)
    
    g.rate_limit_headers = headers
    
    if not allowed:
        audit_logger.log({
            "event": "rate_limit_exceeded",
            "identity": identity,
            "provider": provider_id,
        })
        response = jsonify({"error": {"message": "Rate limit exceeded", "type": "rate_limit_error"}})
        response.status_code = 429
        response.headers["Retry-After"] = str(headers["reset"] - int(time.time()))
        return response


def enforce_provider_rate_limit(provider_id: str):
    """Apply the provider-scoped limit after routing has selected a provider."""
    if not rate_limiter._enabled:
        return None
    identity_info = g.get("identity") or {}
    identity = identity_info.get("identity", "anonymous")
    allowed, headers = rate_limiter.check_rate_limit(identity, provider_id)
    g.rate_limit_headers = headers
    if allowed:
        return None
    audit_logger.log({
        "event": "rate_limit_exceeded",
        "identity": identity,
        "provider": provider_id,
    })
    response = jsonify({"error": {"message": "Rate limit exceeded", "type": "rate_limit_error"}})
    response.status_code = 429
    response.headers["Retry-After"] = str(max(0, headers["reset"] - int(time.time())))
    return response


def audit_middleware(response):
    latency_ms = int((time.time() - g.get("start_time", time.time())) * 1000)
    identity_info = g.get("identity") or {}
    
    audit_logger.log({
        "event": "request_complete",
        "identity": identity_info.get("identity", "anonymous"),
        "provider": getattr(g, "selected_provider_id", "unknown"),
        "model": getattr(g, "request_model", "unknown"),
        "endpoint": request.path,
        "method": request.method,
        "status_code": response.status_code,
        "latency_ms": latency_ms,
        "prompt_tokens": getattr(g, "prompt_tokens", 0),
        "completion_tokens": getattr(g, "completion_tokens", 0),
        "total_tokens": getattr(g, "total_tokens", 0),
        "usage_estimated": getattr(g, "usage_estimated", False),
    })
    
    for key, value in g.get("rate_limit_headers", {}).items():
        response.headers[f"X-RateLimit-{key.capitalize()}"] = str(value)
    
    return response


def require_auth(f: Callable):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_middleware()
        if hasattr(g, "identity") and g.identity.get("identity") == "anonymous" and auth_manager._enabled:
            return jsonify({"error": {"message": "Authentication required", "type": "authentication_error"}}), 401
        return f(*args, **kwargs)
    return decorated


def init_governance(app, config: dict = None):
    config = config or {}
    
    auth_manager._enabled = config.get("auth", {}).get("enabled", True)
    if "api_keys" in config.get("auth", {}):
        auth_manager.load_keys(config["auth"]["api_keys"])
    
    rate_config = config.get("rate_limiting", {})
    rate_limiter._enabled = bool(rate_config.get("enabled", True))
    rate_limiter._default_rate = rate_config.get("default_requests_per_minute", 60)
    for provider, limits in rate_config.get("per_provider", {}).items():
        rate_limiter.set_rate(provider, limits.get("requests_per_minute", 60))
    
    audit_logger._enabled = config.get("audit", {}).get("enabled", True)
    audit_logger._log_file = config.get("audit", {}).get("output", "logs/audit.log")
    
    app.before_request(generate_request_id)
    app.before_request(auth_middleware)
    app.before_request(rate_limit_middleware)
    app.after_request(audit_middleware)
    
    logger.info("Governance middleware initialized")
