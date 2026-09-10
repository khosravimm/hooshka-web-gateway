import os
import yaml
from typing import Any, Dict, Optional


def load_config(config_path: str = "config.yaml") -> Dict[str, Any]:
    if not os.path.exists(config_path):
        return get_default_config()
    
    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f) or {}
    
    merged = merge_with_defaults(config)

    # Runtime secrets belong in the process environment, not tracked YAML.
    # A single local bridge key is sufficient for the current deployment;
    # additional keys may still be supplied through config in non-secret
    # development fixtures.
    env_api_key = os.getenv("BRIDGE_API_KEY")
    if env_api_key:
        identity = os.getenv("BRIDGE_API_IDENTITY", "local-user")
        merged.setdefault("governance", {}).setdefault("auth", {})["enabled"] = True
        merged["governance"]["auth"]["api_keys"] = {
            env_api_key: {"identity": identity, "metadata": {"source": "environment"}}
        }

    return merged


def get_default_config() -> Dict[str, Any]:
    return {
        "server": {
            "host": "127.0.0.1",
            "port": 5000,
            "debug": False,
        },
        "cdp": {
            "url": os.getenv("BRIDGE_CDP_URL", "http://127.0.0.1:9222"),
            "timeout": 30000,
        },
        "chatgpt": {
            "url": os.getenv("BRIDGE_CHATGPT_URL", "https://chatgpt.com"),
            "adapter": os.getenv("BRIDGE_ADAPTER", "dom"),
            "long_text_chunk_size": 2048,
            "request_timeout": 120,
        },
        "providers": [
            {
                "id": "chatgpt-web",
                "type": "chatgpt_web",
                "enabled": True,
                "priority": 100,
                "config": {
                    "cdp_url": os.getenv("BRIDGE_CDP_URL", "http://127.0.0.1:9222"),
                    "chatgpt_url": os.getenv("BRIDGE_CHATGPT_URL", "https://chatgpt.com"),
                    "adapter": os.getenv("BRIDGE_ADAPTER", "dom"),
                    "headless": False,
                    "timeout": 120,
                    "long_text_chunk_size": 2048,
                },
                "capabilities": {
                    "chat_completion": True,
                    # DOM provides buffered OpenAI-compatible streaming and the
                    # provider normalizes Web Chat tool protocol into tool_calls.
                    "streaming": True,
                    "streaming_mode": "buffered",
                    "tools": True,
                    "vision": False,
                    "embeddings": False,
                    "max_context_tokens": 128000,
                    "supported_models": ["chatgpt-web"],
                },
            }
        ],
        "governance": {
            "auth": {
                "enabled": os.getenv("BRIDGE_AUTH_ENABLED", "false").lower() == "true",
                "api_keys": {},
            },
            "rate_limiting": {
                "enabled": True,
                "default_requests_per_minute": int(os.getenv("BRIDGE_RATE_LIMIT", "60")),
                "per_provider": {
                    "chatgpt-web": {"requests_per_minute": 20},
                },
            },
            "audit": {
                "enabled": True,
                "output": "logs/audit.log",
                "format": "json",
                "retention_days": 90,
            },
            "policies": {
                "enabled": False,
                "engine": "opa",
                "bundle_path": "policies/",
            },
        },
        "logging": {
            "level": "INFO",
            "file": "logs/bridge.log",
            "format": "%(asctime)s - %(levelname)s - %(message)s",
            "max_bytes": 10485760,
            "backup_count": 5,
        },
    }


def merge_with_defaults(config: Dict[str, Any]) -> Dict[str, Any]:
    defaults = get_default_config()
    return deep_merge(defaults, config)


def deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def get_env_override(key: str, default: Any = None) -> Any:
    env_key = f"BRIDGE_{key.upper().replace('.', '_')}"
    return os.getenv(env_key, default)