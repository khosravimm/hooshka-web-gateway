import os
import json
import time
import uuid
import logging
import asyncio
import threading
import atexit
import queue
from concurrent.futures import TimeoutError as FutureTimeoutError
from datetime import datetime
from pathlib import Path
from flask import Flask, request, jsonify, Response, stream_with_context, g
from flasgger import Swagger
from core.providers import (
    ProviderConfig,
    ProviderType,
    ProviderCapabilities,
    ProviderError,
    ChatCompletionRequest,
    ModelInfo,
    SessionContext,
)
from core.provider_registry import provider_registry, provider_router
from core.mcp import mcp_translator, mcp_normalizer, mcp_session_manager
from core.governance import init_governance, auth_manager, rate_limiter, enforce_provider_rate_limit
from core.config import load_config
from core.tool_compat import drop_optional_tools_for_text_only_provider, request_requires_tools
from core.functional_readiness import load_readiness
from core.agent_tools import AgentToolRegistry, agent_tool_definitions
from core.agent_execution import AgentLoopPolicy, execute_tool_call, remaining_loop_seconds, summarize_terminal_state
from core.contract_bundle import build_openapi, load_schema_bundle, compatibility_manifest
from core.media_contract import MediaContractError, provider_media_manifest, validate_media_request
from core.provider_targeting import TargetingError, resolve_inference_target, bind_provider_to_target
from core.upload_store import UploadStoreError, save_upload, resolve_upload_ids, delete_upload
from core.feature_settings import (
    apply_feature_defaults,
    persist_provider_feature_defaults,
    provider_feature_state,
)
from adapters.chatgpt_web_provider import create_chatgpt_web_provider
from adapters.qwen_web_provider import create_qwen_web_provider
from adapters.zai_web_provider import create_zai_web_provider
from adapters.deepseek_web_provider import create_deepseek_web_provider
from adapters.discovered_web_provider import create_discovered_web_provider
from control_panel import control_panel_bp


DEFAULT_CONFIG_PATH = os.getenv("HWG_CONFIG_PATH", "config.yaml")


SWAGGER_TEMPLATE = {
    "swagger": "2.0",
    "info": {
        "title": "Hooshka Web Gateway API",
        "description": "Hooshka Web Gateway exposes one governed OpenAI-compatible local API for supported Web-chat providers. Provider-specific browser/session/transport behavior remains behind exact fail-closed routing.",
        "version": "0.7.5",
        "contact": {
            "name": "Hooshka Web Gateway",
        },
        "license": {
            "name": "MIT",
        },
    },
    "host": "localhost:5000",
    "basePath": "/",
    "schemes": ["http"],
    "consumes": ["application/json"],
    "produces": ["application/json", "text/event-stream"],
    "securityDefinitions": {
        "ApiKeyAuth": {
            "type": "apiKey",
            "name": "Authorization",
            "in": "header",
            "description": "Bearer token authentication. Example: 'Bearer sk-your-key'",
        },
    },
    "security": [{"ApiKeyAuth": []}],
    "tags": [
        {"name": "System", "description": "Health and system info"},
        {"name": "Providers", "description": "Provider management and discovery"},
        {"name": "Chat", "description": "Chat completion endpoints"},
    ],
    "definitions": {
        "Error": {
            "type": "object",
            "properties": {
                "error": {
                    "type": "object",
                    "properties": {
                        "message": {"type": "string", "example": "Invalid request"},
                        "type": {"type": "string", "example": "invalid_request_error"},
                        "provider": {"type": "string", "example": "chatgpt-web"},
                        "details": {"type": "object"},
                    },
                },
            },
        },
        "Message": {
            "type": "object",
            "properties": {
                "role": {"type": "string", "enum": ["system", "user", "assistant", "tool"], "example": "user"},
                "content": {"type": "string", "example": "Hello, world!"},
                "tool_calls": {"type": "array", "items": {"type": "object"}},
            },
            "required": ["role", "content"],
        },
        "ChatCompletionRequest": {
            "type": "object",
            "properties": {
                "model": {"type": "string", "example": "gpt-4", "default": "chatgpt-web"},
                "messages": {"type": "array", "items": {"$ref": "#/definitions/Message"}},
                "temperature": {"type": "number", "format": "float", "example": 0.7, "default": 1.0, "minimum": 0, "maximum": 2},
                "top_p": {"type": "number", "format": "float", "example": 1.0, "default": 1.0, "minimum": 0, "maximum": 1},
                "max_tokens": {"type": "integer", "example": 1000, "minimum": 1},
                "stream": {"type": "boolean", "example": False, "default": False},
                "tools": {"type": "array", "items": {"type": "object"}},
                "tool_choice": {"type": "object"},
                "user": {"type": "string", "example": "user-123"},
                "conversation_id": {"type": "string", "example": "conv-abc123"},
                "provider": {"type": "string", "example": "deepseek-web"},
                "profile_id": {"type": "string", "example": "deepseek-web:default"},
                "account_id": {"type": "string", "example": "deepseek-web:default-account"},
                "file_paths": {"type": "array", "items": {"type": "string"}, "example": ["/path/to/file.txt"]},
                "upload_ids": {"type": "array", "items": {"type": "string"}, "description": "Opaque IDs returned by /v1/uploads"},
                "file_path": {"type": "string", "example": "/path/to/file.txt"},
                "long_text": {"type": "boolean", "example": True, "default": True},
            },
            "required": ["messages"],
        },
        "ChatCompletionResponse": {
            "type": "object",
            "properties": {
                "id": {"type": "string", "example": "chatcmpl-abc123"},
                "object": {"type": "string", "example": "chat.completion"},
                "created": {"type": "integer", "example": 1699300000},
                "model": {"type": "string", "example": "gpt-4"},
                "choices": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "index": {"type": "integer", "example": 0},
                            "message": {"$ref": "#/definitions/Message"},
                            "finish_reason": {"type": "string", "enum": ["stop", "length", "tool_calls", "content_filter"], "example": "stop"},
                        },
                    },
                },
                "usage": {
                    "type": "object",
                    "properties": {
                        "prompt_tokens": {"type": "integer", "example": 10},
                        "completion_tokens": {"type": "integer", "example": 20},
                        "total_tokens": {"type": "integer", "example": 30},
                    },
                },
                "provider_meta": {"type": "object"},
            },
        },
        "ChatCompletionChunk": {
            "type": "object",
            "properties": {
                "id": {"type": "string", "example": "chatcmpl-abc123"},
                "object": {"type": "string", "example": "chat.completion.chunk"},
                "created": {"type": "integer", "example": 1699300000},
                "model": {"type": "string", "example": "gpt-4"},
                "choices": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "index": {"type": "integer", "example": 0},
                            "delta": {
                                "type": "object",
                                "properties": {
                                    "role": {"type": "string", "enum": ["assistant"]},
                                    "content": {"type": "string"},
                                    "tool_calls": {"type": "array", "items": {"type": "object"}},
                                },
                            },
                            "finish_reason": {"type": ["string", "null"], "enum": ["stop", "length", "tool_calls", "content_filter", "null"]},
                        },
                    },
                },
                "provider_meta": {"type": "object"},
            },
        },
        "Provider": {
            "type": "object",
            "properties": {
                "id": {"type": "string", "example": "chatgpt-web"},
                "type": {"type": "string", "example": "chatgpt_web"},
                "enabled": {"type": "boolean", "example": True},
                "priority": {"type": "integer", "example": 100},
                "capabilities": {
                    "type": "object",
                    "properties": {
                        "chat_completion": {"type": "boolean"},
                        "streaming": {"type": "boolean"},
                        "tools": {"type": "boolean"},
                        "vision": {"type": "boolean"},
                        "embeddings": {"type": "boolean"},
                        "max_context_tokens": {"type": "integer"},
                        "supported_models": {"type": "array", "items": {"type": "string"}},
                    },
                },
            },
        },
        "Model": {
            "type": "object",
            "properties": {
                "id": {"type": "string", "example": "gpt-4"},
                "object": {"type": "string", "example": "model"},
                "owned_by": {"type": "string", "example": "openai"},
                "provider": {"type": "string", "example": "chatgpt-web"},
            },
        },
        "CodeBlock": {
            "type": "object",
            "properties": {
                "language": {"type": "string", "example": "python"},
                "code": {"type": "string", "example": "print('Hello, world!')"},
            },
        },
        "CodeChatResponse": {
            "allOf": [
                {"$ref": "#/definitions/ChatCompletionResponse"},
                {
                    "type": "object",
                    "properties": {
                        "code": {
                            "type": "object",
                            "properties": {
                                "blocks": {"type": "array", "items": {"$ref": "#/definitions/CodeBlock"}},
                                "language": {"type": "string"},
                                "count": {"type": "integer"},
                                "saved_to": {"type": "string"},
                            },
                        },
                    },
                },
            ],
        },
        "ConversationResponse": {
            "allOf": [
                {"$ref": "#/definitions/ChatCompletionResponse"},
                {
                    "type": "object",
                    "properties": {
                        "conversation_id": {"type": "string", "example": "conv-abc123"},
                    },
                },
            ],
        },
        "ModesResponse": {
            "type": "object",
            "properties": {
                "providers": {"type": "array", "items": {"$ref": "#/definitions/Provider"}},
                "default": {"type": "string", "example": "chatgpt-web"},
            },
        },
        "ModelsResponse": {
            "type": "object",
            "properties": {
                "object": {"type": "string", "example": "list"},
                "data": {"type": "array", "items": {"$ref": "#/definitions/Model"}},
            },
        },
        "HealthResponse": {
            "type": "object",
            "properties": {
                "status": {"type": "string", "example": "ok"},
            },
        },
    },
}


def create_app(config_path: str | None = None) -> Flask:
    config_path = config_path or DEFAULT_CONFIG_PATH
    config = load_config(config_path)

    app = Flask(__name__)
    input_limits = (config.get("governance", {}) or {}).get("input_limits", {}) or {}
    app.config["MAX_CONTENT_LENGTH"] = int(input_limits.get("max_request_bytes", 8 * 1024 * 1024))

    Swagger(app, template=SWAGGER_TEMPLATE, config={
        "headers": [],
        "specs": [
            {
                "endpoint": "apispec",
                "route": "/apispec.json",
                "rule_filter": lambda rule: True,
                "model_filter": lambda tag: True,
            }
        ],
        "static_url_path": "/flasgger_static",
        "swagger_ui": True,
        "specs_route": "/docs/",
    })

    # Register control panel
    app.register_blueprint(control_panel_bp)

    os.makedirs("logs", exist_ok=True)

    logging.basicConfig(
        filename=config["logging"]["file"],
        level=getattr(logging, config["logging"]["level"]),
        format=config["logging"]["format"],
    )
    logger = logging.getLogger(__name__)

    # HTTP liveness must not share fate with slow/stuck Web-chat provider work.
    # Keep Web-chat provider work bounded and separate from the configurable
    # Waitress HTTP worker pool. Provider overload returns explicit backpressure
    # while fast liveness/readiness/model endpoints keep responding.
    provider_concurrency = int(
        os.getenv(
            "HOOSHKA_GW_PROVIDER_CONCURRENCY",
            str(config.get("server", {}).get("provider_concurrency", 2)),
        )
    )
    provider_concurrency = max(1, provider_concurrency)
    _provider_slots = threading.BoundedSemaphore(provider_concurrency)
    _provider_state_lock = threading.Lock()
    _provider_inflight = 0
    _provider_rejected = 0
    _provider_timeouts = 0

    def _provider_state() -> dict:
        with _provider_state_lock:
            return {
                "max_concurrency": provider_concurrency,
                "inflight": _provider_inflight,
                "rejected": _provider_rejected,
                "timeouts": _provider_timeouts,
            }

    def _try_acquire_provider_slot(kind: str, provider_id: str = "unknown") -> bool:
        nonlocal _provider_inflight, _provider_rejected
        acquired = _provider_slots.acquire(blocking=False)
        with _provider_state_lock:
            if acquired:
                _provider_inflight += 1
                logger.info("Provider slot acquired: kind=%s provider=%s inflight=%s/%s", kind, provider_id, _provider_inflight, provider_concurrency)
            else:
                _provider_rejected += 1
                logger.warning("Provider worker pool busy: kind=%s provider=%s inflight=%s/%s rejected=%s", kind, provider_id, _provider_inflight, provider_concurrency, _provider_rejected)
        return acquired

    def _release_provider_slot(kind: str, provider_id: str = "unknown") -> None:
        nonlocal _provider_inflight
        with _provider_state_lock:
            _provider_inflight = max(0, _provider_inflight - 1)
            logger.info("Provider slot released: kind=%s provider=%s inflight=%s/%s", kind, provider_id, _provider_inflight, provider_concurrency)
        try:
            _provider_slots.release()
        except ValueError:
            logger.error("Provider slot release called without matching acquire")

    def _provider_busy_response(kind: str, provider_id: str = "unknown"):
        return jsonify({
            "error": {
                "message": "Provider worker pool is busy; retry later.",
                "type": "server_overloaded",
                "code": "provider_busy",
                "provider": provider_id,
                "operation": kind,
                "details": _provider_state(),
            }
        }), 503

    def _static_models_for_provider(provider) -> list[ModelInfo]:
        ids = list(getattr(provider.capabilities, "supported_models", []) or [])
        if provider.provider_id not in ids:
            ids.insert(0, provider.provider_id)

        cfg = getattr(provider.config, "config", {}) or {}
        default_upstream = cfg.get("default_upstream_model")
        namespace = cfg.get("model_namespace")
        if namespace and default_upstream:
            ids.append(f"{namespace}:{default_upstream}")

        seen = set()
        models = []
        for mid in ids:
            if not mid or mid in seen:
                continue
            seen.add(mid)
            models.append(ModelInfo(id=mid, owned_by=provider.provider_id, provider=provider.provider_id))
        return models

    def _providers_summary(enabled_only: bool = True) -> list[dict]:
        return [
            {
                "id": p.provider_id,
                "type": p.provider_type.value,
                "enabled": p.config.enabled,
                "priority": p.config.priority,
                "capabilities": {
                    "chat_completion": p.capabilities.chat_completion,
                    "streaming": p.capabilities.streaming,
                    "streaming_mode": p.capabilities.streaming_mode,
                    "tools": p.capabilities.tools,
                    "vision": p.capabilities.vision,
                    "embeddings": p.capabilities.embeddings,
                    "max_context_tokens": p.capabilities.max_context_tokens,
                    "supported_models": p.capabilities.supported_models,
                    "search": p.capabilities.search,
                    "reasoning": p.capabilities.reasoning,
                    "files": p.capabilities.files,
                    "media": provider_media_manifest(p),
                    "transport_mode": p.capabilities.transport_mode,
                },
                "features": provider_feature_state(p),
            }
            for p in provider_registry.list_providers(enabled_only=enabled_only)
        ]

    init_governance(app, config["governance"])

    def _provider_rpm(provider_id: str) -> int:
        rate_limiting = config.get("governance", {}).get("rate_limiting", {}) or {}
        per = rate_limiting.get("per_provider", {}) or {}
        entry = per.get(provider_id)
        if isinstance(entry, dict) and entry.get("requests_per_minute"):
            return int(entry["requests_per_minute"])
        return int(rate_limiting.get("default_requests_per_minute", 60))

    for provider_config in config["providers"]:
        # Register disabled providers as inventory entries. Runtime routing
        # continues to use enabled_only filtering in provider_registry.
        # This keeps discovery APIs aligned with the Provider Profile model.

        pconfig = ProviderConfig(
            provider_id=provider_config["id"],
            provider_type=ProviderType(provider_config["type"]),
            enabled=provider_config.get("enabled", True),
            priority=provider_config.get("priority", 100),
            config=provider_config.get("config", {}),
            capabilities=ProviderCapabilities(**provider_config.get("capabilities", {})),
        )

        provisioned = None
        if pconfig.provider_type == ProviderType.CHATGPT_WEB:
            chat_overrides = {
                k: v for k, v in pconfig.config.items()
                if k not in {"adapter", "cdp_url", "chatgpt_url"}
            }
            if pconfig.config.get("cdp_url"):
                chat_overrides["cdp_url"] = pconfig.config["cdp_url"]
            if pconfig.config.get("chatgpt_url"):
                chat_overrides["chatgpt_url"] = pconfig.config["chatgpt_url"]
            provisioned = create_chatgpt_web_provider(
                provider_id=pconfig.provider_id,
                adapter=pconfig.config.get("adapter", "dom"),
                priority=pconfig.priority,
                enabled=pconfig.enabled,
                **chat_overrides,
            )
        elif pconfig.provider_type == ProviderType.QWEN_WEB:
            provisioned = create_qwen_web_provider(
                provider_id=pconfig.provider_id,
                priority=pconfig.priority,
                enabled=pconfig.enabled,
                **pconfig.config,
            )
        elif pconfig.provider_type == ProviderType.ZAI_WEB:
            provisioned = create_zai_web_provider(
                provider_id=pconfig.provider_id,
                priority=pconfig.priority,
                enabled=pconfig.enabled,
                **pconfig.config,
            )
        elif pconfig.provider_type == ProviderType.DEEPSEEK_WEB:
            provisioned = create_deepseek_web_provider(
                provider_id=pconfig.provider_id,
                priority=pconfig.priority,
                enabled=pconfig.enabled,
                **pconfig.config,
            )
        elif pconfig.provider_type == ProviderType.CUSTOM and pconfig.config.get("adapter_kind") == "discovered_web":
            root = Path(__file__).resolve().parent
            allowed_root = (root / "docs" / "profiles").resolve()
            raw_profile = str(pconfig.config.get("adapter_profile_path") or "").strip()
            try:
                profile_path = Path(raw_profile)
                if not profile_path.is_absolute():
                    profile_path = root / profile_path
                profile_path = profile_path.resolve()
                if allowed_root != profile_path and allowed_root not in profile_path.parents:
                    raise ValueError("adapter profile path outside docs/profiles")
                artifact = json.loads(profile_path.read_text(encoding="utf-8"))
                if artifact.get("status") != "E2_CONFORMANT_CANDIDATE":
                    raise ValueError("adapter profile is not E2 conformant")
                if str(artifact.get("provider_id") or "") != pconfig.provider_id:
                    raise ValueError("adapter profile provider id mismatch")
                candidate = artifact.get("adapter_candidate") or {}
                provisioned = create_discovered_web_provider(
                    provider_id=pconfig.provider_id,
                    cdp_url=str(pconfig.config.get("cdp_url") or ""),
                    home_url=str(pconfig.config.get("home_url") or candidate.get("home_url") or ""),
                    adapter_candidate=candidate,
                    priority=pconfig.priority,
                    enabled=pconfig.enabled,
                    timeout_seconds=float(pconfig.config.get("timeout_seconds") or 60.0),
                )
            except Exception as exc:
                logger.error("Discovered provider %s rejected fail-closed: %s", pconfig.provider_id, exc)
                provisioned = None

        if provisioned is not None:
            try:
                from core.profile_store import load_ng_inventory
                from core.media_qualification import apply_persisted_media_certification
                apply_persisted_media_certification(provisioned, load_ng_inventory(config_path))
            except Exception as exc:
                logger.debug("No persisted media certification applied for %s: %s", provisioned.provider_id, type(exc).__name__)
            provider_registry.register(provisioned)
            rate_limiter.set_rate(provisioned.provider_id, _provider_rpm(provisioned.provider_id))

    # ADR-002 pilot wiring (opt-in, default off): when
    # runtime_orchestration.shared_browser.enabled is true, bind the
    # chatgpt-web provider to the shared pool. Disabled/absent -> legacy.
    try:
        from core.browser_pool import shared_browser_from_config
        _pool = shared_browser_from_config(config)
    except Exception as e:
        logger.warning(f"Shared browser pool unavailable: {e}")
        _pool = None
    if _pool is not None:
        _chatgpt = provider_registry.get("chatgpt-web")
        if _chatgpt is not None and hasattr(_chatgpt, "bind_shared_pool"):
            _chatgpt.bind_shared_pool(_pool)
            logger.info(f"Shared browser pool bound: {_pool.cdp_url}")
    app.config["HWG_SHARED_POOL"] = _pool

    default_provider = provider_registry.get_default()
    default_model_id = default_provider.provider_id if default_provider else ""

    server_config = config["server"]
    from core.security_gate import assert_release_security_config
    assert_release_security_config(config)

    def _hydrate_upload_ids(data: dict) -> dict:
        hydrated = dict(data or {})
        upload_ids = hydrated.get("upload_ids") or []
        if isinstance(upload_ids, str):
            upload_ids = [upload_ids]
        if not isinstance(upload_ids, list):
            raise UploadStoreError("upload_ids must be an array", "invalid_upload_ids", 400)
        if len(upload_ids) > 8:
            raise UploadStoreError("Too many uploads in one request", "too_many_uploads", 400)
        if not upload_ids:
            return hydrated
        paths, metadata = resolve_upload_ids(upload_ids)
        existing = list(hydrated.get("file_paths") or [])
        if hydrated.get("file_path"):
            existing.append(hydrated.get("file_path"))
        hydrated["file_paths"] = existing + paths
        hydrated.pop("file_path", None)
        hydrated["resolved_uploads"] = metadata
        return hydrated

    def _build_request(data: dict) -> ChatCompletionRequest:
        def _content_to_text(content) -> str:
            if isinstance(content, str):
                return content
            if isinstance(content, list):
                parts = []
                for item in content:
                    if isinstance(item, str):
                        parts.append(item)
                    elif isinstance(item, dict) and item.get("type") in ("text", "input_text"):
                        parts.append(str(item.get("text", "")))
                return "".join(parts)
            return "" if content is None else str(content)

        messages = []
        for message in data.get("messages", []):
            normalized_message = dict(message)
            normalized_message["content"] = _content_to_text(message.get("content", ""))
            messages.append(normalized_message)

        return ChatCompletionRequest(
            model=data.get("model") or default_model_id,
            messages=messages,
            temperature=data.get("temperature", 1.0),
            top_p=data.get("top_p", 1.0),
            max_tokens=data.get("max_tokens"),
            stream=data.get("stream", False),
            tools=data.get("tools"),
            tool_choice=data.get("tool_choice"),
            user=data.get("user"),
            conversation_id=data.get("conversation_id"),
            provider_options={
                "file_paths": data.get("file_paths") or ([data.get("file_path")] if data.get("file_path") else []),
                "long_text": data.get("long_text", True),
                "language": data.get("language"),
                "code_only": data.get("code_only", False),
                "save_to": data.get("save_to"),
                "thinking": data.get("thinking"),
                "search": data.get("search"),
                "upstream_model": data.get("upstream_model"),
            },
        )

    def _estimate_request_prompt_tokens(req: ChatCompletionRequest) -> int:
        total_chars = 0
        for message in req.messages or []:
            total_chars += len(str(message.get("role", "")))
            total_chars += len(str(message.get("content", "")))
        return max(1, total_chars // 4) if total_chars else 0

    def _finalize_usage_for_audit(req: ChatCompletionRequest, normalized) -> None:
        usage = normalized.usage
        estimated = bool((normalized.provider_meta or {}).get("usage_estimated"))
        if usage.prompt_tokens == 0:
            usage.prompt_tokens = _estimate_request_prompt_tokens(req)
            estimated = True
        if usage.total_tokens == 0:
            usage.total_tokens = usage.prompt_tokens + usage.completion_tokens
            estimated = True
        elif usage.total_tokens < usage.prompt_tokens + usage.completion_tokens:
            usage.total_tokens = usage.prompt_tokens + usage.completion_tokens
            estimated = True
        if estimated:
            normalized.provider_meta = normalized.provider_meta or {}
            normalized.provider_meta["usage_estimated"] = True
            normalized.provider_meta.setdefault("usage_estimation_method", "text_chars_div_4")
        g.prompt_tokens = usage.prompt_tokens
        g.completion_tokens = usage.completion_tokens
        g.total_tokens = usage.total_tokens
        g.usage_estimated = estimated

    def _resolve_inference_provider(data: dict, req: ChatCompletionRequest):
        target = resolve_inference_target(data, config_path)
        provider_id = target.provider_id if target else str(data.get("provider") or "").strip() or None
        base = provider_router.select_provider(
            model=req.model, provider_id=provider_id,
            require_streaming=req.stream, require_tools=request_requires_tools(req),
        )
        if base is None:
            return None, target, False
        provider, temporary = bind_provider_to_target(base, target, config_path)
        req.provider_options = req.provider_options or {}
        if target:
            req.provider_options["inference_target"] = target.metadata()
        return provider, target, temporary

    def _target_error(exc: TargetingError):
        return jsonify({"error": {"message": str(exc), "type": "invalid_request_error", "code": exc.code, "details": exc.details}}), exc.status

    def _annotate_inference_target(normalized, req: ChatCompletionRequest):
        target=(req.provider_options or {}).get("inference_target")
        if target:
            normalized.provider_meta = normalized.provider_meta or {}
            normalized.provider_meta["inference_target"] = target
        return normalized

    def _validate_request(req: ChatCompletionRequest) -> tuple[bool, str]:
        if not req.messages:
            return False, "messages is required"

        user_messages = [m for m in req.messages if m.get("role") == "user"]
        if not user_messages:
            return False, "No user message provided"

        message = user_messages[-1].get("content", "")
        if not isinstance(message, str):
            message = str(message)
        message = message.strip()
        if not message:
            return False, "Empty user message"

        return True, ""

    def _format_response(response, provider) -> dict:
        return {
            "id": response.id,
            "object": response.object,
            "created": response.created,
            "model": response.model,
            "choices": [
                {
                    "index": c.index,
                    "message": {
                        "role": c.message.role,
                        "content": c.message.content,
                        "tool_calls": c.message.tool_calls,
                    },
                    "finish_reason": c.finish_reason,
                }
                for c in response.choices
            ],
            "usage": {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            },
            "provider_meta": response.provider_meta,
        }

    def _http_status_for_error(error: Exception) -> int:
        if isinstance(error, ProviderError) and error.code in {"invalid_model", "model_not_found"}:
            return 404
        if isinstance(error, ProviderError) and error.code in {"authentication_failed", "auth_required"}:
            return 401
        if isinstance(error, ProviderError) and error.code == "generation_cancelled":
            return 409
        if isinstance(error, ProviderError) and error.code in {
            "unsupported_feature",
            "unsupported_tools",
        }:
            return 400
        return 500

    def _format_stream_chunk(chunk) -> dict:
        return {
            "id": chunk.id,
            "object": chunk.object,
            "created": chunk.created,
            "model": chunk.model,
            "choices": [
                {
                    "index": c.index,
                    "delta": {
                        "role": c.delta.role,
                        "content": c.delta.content,
                        "tool_calls": c.delta.tool_calls,
                    },
                    "finish_reason": c.finish_reason,
                }
                for c in chunk.choices
            ],
            "provider_meta": chunk.provider_meta,
        }

    def _get_session(req: ChatCompletionRequest, provider=None, create: bool = False) -> SessionContext | None:
        if not req.conversation_id:
            return None
        if create:
            if provider is None:
                raise ValueError("provider is required when creating a conversation session")
            session_data = mcp_session_manager.get_or_create_session(req.conversation_id, provider)
        else:
            session_data = mcp_session_manager.get_session(req.conversation_id)
        return SessionContext(
            conversation_id=req.conversation_id,
            provider_session_id=session_data.get("provider_session_id") if session_data else None,
            metadata=session_data.get("metadata", {}) if session_data else {},
        )

    # Playwright objects are bound to the event loop in which they were
    # created.  Flask handlers run in different request contexts, so using
    # asyncio.run() here creates a new loop for every request and invalidates
    # the reused Playwright connection after the first call.  Keep one loop
    # alive for the lifetime of the process and submit all provider work to it.
    _async_loop = asyncio.new_event_loop()
    _async_thread = threading.Thread(
        target=_async_loop.run_forever,
        name="web-llm-async-loop",
        daemon=True,
    )
    _async_thread.start()
    app.config["HWG_ASYNC_LOOP"] = _async_loop

    def _run_async(coro, timeout: float | None = None):
        nonlocal _provider_timeouts
        future = asyncio.run_coroutine_threadsafe(coro, _async_loop)
        try:
            return future.result(timeout=timeout)
        except FutureTimeoutError:
            future.cancel()
            with _provider_state_lock:
                _provider_timeouts += 1
            logger.warning("Provider async operation timed out after %s seconds", timeout)
            raise

    def _shutdown_async_loop():
        if not _async_loop.is_running():
            return
        try:
            future = asyncio.run_coroutine_threadsafe(provider_registry.close_all(), _async_loop)
            future.result(timeout=10)
        except Exception as e:
            logger.warning(f"Provider shutdown did not complete cleanly: {e}")
        finally:
            _async_loop.call_soon_threadsafe(_async_loop.stop)

    atexit.register(_shutdown_async_loop)

    @app.route("/health", methods=["GET"])
    def health():
        """
        Health Check
        ---
        tags:
          - System
        summary: Check service health
        responses:
          200:
            description: Service is healthy
            schema:
              $ref: '#/definitions/HealthResponse'
        """
        return jsonify({
            "status": "ok",
            "service": "hooshka-web-gateway",
            "legacy_service": "mcp-web-bridge",
            "provider_runtime": _provider_state(),
        })

    @app.route("/ready", methods=["GET"])
    def ready():
        """Fast readiness from the latest bounded functional-readiness evidence.

        This endpoint never probes Web-chat providers directly. A Provider is
        READY only while a non-expired functional readiness record exists.
        """
        providers = provider_registry.list_providers()
        state = _provider_state()
        details=[]
        ready_any=False
        for p in providers:
            record=load_readiness(p.provider_id)
            current_ready=bool(record and record.get("current") and record.get("ready") and record.get("state")=="READY")
            ready_any = ready_any or current_ready
            details.append({
                "provider":p.provider_id,
                "registered":True,
                "ready":current_ready,
                "readiness":record or {"state":"UNKNOWN","ready":False,"current":False},
                "capabilities":{
                    "chat_completion":p.capabilities.chat_completion,
                    "streaming":p.capabilities.streaming,
                    "transport_mode":p.capabilities.transport_mode,
                },
            })
        return jsonify({
            "status":"ready" if ready_any else "not_ready",
            "mode":"functional_cache",
            "provider_runtime":state,
            "providers":details,
        }), (200 if ready_any else 503)

    @app.route("/health/deep", methods=["GET"])
    def deep_health():
        """Bounded deep provider readiness check.

        It is intentionally separate from /health and /ready, and it uses the
        provider worker semaphore so it cannot consume all HTTP workers.
        """
        if not _try_acquire_provider_slot("deep_health", "all"):
            return _provider_busy_response("deep_health", "all")
        try:
            providers = provider_registry.list_providers()
            async def probe_provider(provider):
                try:
                    ok = bool(await asyncio.wait_for(provider.health_check(), timeout=2.0))
                except Exception as e:
                    ok = False
                    logger.warning(f"Deep readiness check failed for {provider.provider_id}: {e}")
                return {"provider": provider.provider_id, "ready": ok}

            async def probe_all():
                return await asyncio.gather(*(probe_provider(p) for p in providers))

            details = _run_async(probe_all(), timeout=3.0) if providers else []
            ready_any = any(item.get("ready") for item in details)
            return jsonify({
                "status": "ready" if ready_any else "not_ready",
                "mode": "deep",
                "provider_runtime": _provider_state(),
                "providers": details,
            }), (200 if ready_any else 503)
        finally:
            _release_provider_slot("deep_health", "all")

    @app.route("/modes", methods=["GET"])
    def list_modes():
        """
        List Available Providers
        ---
        tags:
          - Providers
        summary: Get list of registered providers with capabilities
        responses:
          200:
            description: List of providers
            schema:
              $ref: '#/definitions/ModesResponse'
        """
        providers = provider_registry.list_providers()
        return jsonify({
            "providers": _providers_summary(enabled_only=False),
            "default": provider_registry.get_default().provider_id if provider_registry.get_default() else None,
        })

    @app.route("/v1/providers", methods=["GET"])
    def v1_list_providers():
        """
        List Providers (v1)
        ---
        tags:
          - Providers
        summary: OpenAI-adjacent discovery of registered providers and capabilities
        responses:
          200:
            description: List of providers with capabilities
        """
        return jsonify({
            "object": "list",
            "providers": _providers_summary(enabled_only=False),
            "default": provider_registry.get_default().provider_id if provider_registry.get_default() else None,
        })

    @app.route("/v1/contracts/openapi.json", methods=["GET"])
    def v1_contract_openapi():
        return jsonify(build_openapi(app))

    @app.route("/v1/contracts/schemas", methods=["GET"])
    def v1_contract_schemas():
        return jsonify(load_schema_bundle())

    @app.route("/v1/compatibility", methods=["GET"])
    def v1_compatibility_manifest():
        return jsonify(compatibility_manifest())

    @app.route("/v1/capabilities", methods=["GET"])
    def v1_capabilities():
        """
        Capability Manifest (v1)
        ---
        tags:
          - Providers
        summary: Versioned capability manifest for automatic discovery by agents
        responses:
          200:
            description: Capability manifest
        """
        governance_config = config.get("governance", {})
        auth_enabled = bool(governance_config.get("auth", {}).get("enabled", True))
        return jsonify({
            "manifest_version": "1.0",
            "spec_version": "1.0.0-dev.0",
            "compatibility_baseline": "openai-2026-09-20",
            "generated_at": int(time.time()),
            "providers": _providers_summary(enabled_only=False),
            "access": {
                "loopback_without_key": True,
                "loopback_policy": "local_trust_configurable",
                "non_loopback": "api_key_required",
                "auth_enabled": auth_enabled,
            },
        })

    @app.route("/v1/providers/<provider_id>/features", methods=["GET", "PUT"])
    def provider_features(provider_id: str):
        provider = provider_registry.get(provider_id)
        if provider is None:
            return jsonify({"error": {
                "message": f"Unknown provider: {provider_id}",
                "type": "invalid_request_error",
                "code": "unknown_provider",
            }}), 404

        if request.method == "GET":
            return jsonify({
                "provider": provider_id,
                "features": provider_feature_state(provider),
            })

        body = request.get_json(force=True) or {}
        requested = body.get("defaults", body)
        if not isinstance(requested, dict):
            return jsonify({"error": {
                "message": "Feature settings must be an object",
                "type": "invalid_request_error",
                "code": "invalid_feature_setting",
            }}), 400

        try:
            state = persist_provider_feature_defaults(provider, requested, config_path)
        except ValueError as exc:
            return jsonify({"error": {
                "message": str(exc),
                "type": "invalid_request_error",
                "code": "invalid_feature_setting",
            }}), 400
        except Exception as exc:
            logger.exception("Failed to persist provider feature settings")
            return jsonify({"error": {
                "message": str(exc),
                "type": "configuration_error",
                "code": "feature_settings_persist_failed",
            }}), 500

        return jsonify({
            "provider": provider_id,
            "features": state,
            "persisted": True,
        })

    @app.route("/v1/uploads", methods=["POST"])
    def create_uploads():
        files = request.files.getlist("files") or request.files.getlist("file")
        files = [f for f in files if getattr(f, "filename", "")]
        if not files:
            return jsonify({"error":{"message":"No upload files supplied","type":"invalid_request_error","code":"upload_required"}}), 400
        if len(files) > 8:
            return jsonify({"error":{"message":"At most 8 files may be uploaded per request","type":"invalid_request_error","code":"too_many_uploads"}}), 400
        provider_id = str(request.form.get("provider") or "").strip()
        provider = provider_registry.get(provider_id) if provider_id else None
        if provider_id and provider is None:
            return jsonify({"error":{"message":f"Unknown provider: {provider_id}","type":"invalid_request_error","code":"unknown_provider"}}), 404
        saved = []
        try:
            for item in files:
                saved.append(save_upload(item.stream, item.filename, item.mimetype or "application/octet-stream"))
            if provider is not None:
                paths, _ = resolve_upload_ids([x["id"] for x in saved])
                validate_media_request(provider, {"file_paths": paths})
            return jsonify({"object":"list","data":saved}), 201
        except MediaContractError as exc:
            for item in saved: delete_upload(item.get("id"))
            return jsonify({"error":{"message":str(exc),"type":"invalid_request_error","code":exc.code,"provider":provider_id,"details":exc.details}}), 400
        except UploadStoreError as exc:
            for item in saved: delete_upload(item.get("id"))
            return jsonify({"error":{"message":str(exc),"type":"invalid_request_error","code":exc.code}}), exc.status

    @app.route("/v1/uploads/<upload_id>", methods=["DELETE"])
    def delete_uploaded_file(upload_id: str):
        return jsonify({"deleted": bool(delete_upload(upload_id)), "id": upload_id})

    @app.route("/v1/models", methods=["GET"])
    def list_models():
        """
        List Available Models
        ---
        tags:
          - Providers
        summary: Get list of available models across all providers
        responses:
          200:
            description: List of models
            schema:
              $ref: '#/definitions/ModelsResponse'
        """
        all_models = []
        for provider in provider_registry.list_providers():
            all_models.extend(_static_models_for_provider(provider))

        return jsonify({
            "object": "list",
            "mode": "fast_static",
            "provider_runtime": _provider_state(),
            "data": [
                {"id": m.id, "object": m.object, "owned_by": m.owned_by, "provider": m.provider}
                for m in all_models
            ],
        })

    @app.route("/v1/chat/completions", methods=["POST"])
    def chat_completions():
        """
        Chat Completion
        ---
        tags:
          - Chat
        summary: Create a chat completion (OpenAI-compatible)
        parameters:
          - in: body
            name: body
            required: true
            schema:
              $ref: '#/definitions/ChatCompletionRequest'
        responses:
          200:
            description: Successful response
            schema:
              $ref: '#/definitions/ChatCompletionResponse'
          400:
            description: Invalid request
            schema:
              $ref: '#/definitions/Error'
          503:
            description: No provider available
            schema:
              $ref: '#/definitions/Error'
        """
        try:
            data = _hydrate_upload_ids(request.get_json(force=True) or {})
        except UploadStoreError as exc:
            return jsonify({"error":{"message":str(exc),"type":"invalid_request_error","code":exc.code}}), exc.status
        req = _build_request(data)

        valid, error_msg = _validate_request(req)
        if not valid:
            return jsonify({"error": {"message": error_msg, "type": "invalid_request_error"}}), 400

        g.request_model = req.model

        try:
            provider, inference_target, temporary_provider = _resolve_inference_provider(data, req)
        except TargetingError as exc:
            return _target_error(exc)
        if not provider:
            return jsonify({"error": {
                "message": f"No enabled provider supports model '{req.model}' with the requested capabilities (including optional vs required tool support).",
                "type": "invalid_request_error",
                "code": "model_not_found",
                "details": {"requested_tools": bool(req.tools), "tool_choice": req.tool_choice},
            }}), 404

        g.selected_provider_id = provider.provider_id
        apply_feature_defaults(req, provider)
        drop_optional_tools_for_text_only_provider(req, provider)
        try:
            media_state = validate_media_request(provider, data)
        except MediaContractError as exc:
            return jsonify({"error": {
                "message": str(exc), "type": "invalid_request_error", "code": exc.code,
                "provider": provider.provider_id, "details": exc.details,
            }}), 400
        req.provider_options = req.provider_options or {}
        req.provider_options["media_contract"] = media_state
        rate_response = enforce_provider_rate_limit(provider.provider_id)
        if rate_response is not None:
            return rate_response

        if not _try_acquire_provider_slot("chat_completions", provider.provider_id):
            return _provider_busy_response("chat_completions", provider.provider_id)

        try:
            translated_req = mcp_translator.translate_request(req, provider)
            session = _get_session(req)

            if req.stream:
                return _stream_response(provider, translated_req, session, "chat_completions", close_provider=temporary_provider)
            else:
                response = _run_async(provider.chat_completion(translated_req, session), timeout=240)
                normalized = _annotate_inference_target(mcp_normalizer.normalize_response(response, provider, translated_req), req)

                if session and normalized.provider_meta.get("conversation_id"):
                    mcp_session_manager.update_provider_session_id(
                        req.conversation_id,
                        normalized.provider_meta["conversation_id"]
                    )

                _finalize_usage_for_audit(req, normalized)

                return jsonify(_format_response(normalized, provider))
        except Exception as e:
            logger.error(f"Chat completion error: {e}")
            error_resp = mcp_normalizer.normalize_error(e, provider)
            return jsonify(error_resp), _http_status_for_error(e)
        finally:
            if not req.stream:
                _release_provider_slot("chat_completions", provider.provider_id)
                if temporary_provider:
                    try: _run_async(provider.close(), timeout=10)
                    except Exception: logger.debug("Target provider cleanup failed", exc_info=True)

    @app.route("/v1/chat/cancel", methods=["POST"])
    def cancel_chat_generation():
        data = request.get_json(silent=True) or {}
        conversation_id = str(data.get("conversation_id") or "").strip()
        requested_provider = str(data.get("provider") or "").strip()
        reason = str(data.get("reason") or "client_cancel").strip()[:160] or "client_cancel"
        session = mcp_session_manager.get_session(conversation_id) if conversation_id else None
        session_provider = str((session or {}).get("provider_id") or "").strip()
        if requested_provider and session_provider and requested_provider != session_provider:
            return jsonify({"error": {"message": "provider does not match conversation", "type": "invalid_request_error", "code": "conversation_provider_mismatch", "details": {"conversation_id": conversation_id, "provider": requested_provider, "session_provider": session_provider}}}), 409
        provider_id = requested_provider or session_provider
        if not provider_id:
            return jsonify({"error": {"message": "provider or known conversation_id is required", "type": "invalid_request_error", "code": "cancel_target_required"}}), 400
        provider = provider_registry.get(provider_id)
        if provider is None:
            return jsonify({"error": {"message": f"Unknown provider: {provider_id}", "type": "invalid_request_error", "code": "unknown_provider"}}), 404
        try:
            result = _run_async(provider.cancel_active_generation(reason), timeout=10) or {}
            payload = {"object": "chat.cancel.result", "provider": provider_id, "conversation_id": conversation_id or None, "reason": reason, **dict(result)}
            return jsonify(payload), (200 if payload.get("supported", True) else 409)
        except Exception as exc:
            logger.warning("Public cancellation failed for %s", provider_id, exc_info=True)
            return jsonify({"error": {"message": str(exc), "type": "provider_error", "code": "cancel_failed", "provider": provider_id}}), 502

    @app.route("/v1/responses", methods=["POST"])
    def create_response():
        """
        Create Response
        ---
        tags:
          - Chat
        summary: Create a response (OpenAI Responses API, normalized onto chat)
        responses:
          200:
            description: Response object
          400:
            description: Invalid request or unsupported streaming
        """
        data = request.get_json(force=True) or {}
        if data.get("stream"):
            return jsonify({"error": {
                "message": "Streaming is not supported on /v1/responses; use /v1/chat/completions with stream=true.",
                "type": "invalid_request_error",
                "code": "unsupported_streaming",
            }}), 400
        raw_input = data.get("input", "")
        if isinstance(raw_input, str):
            messages = [{"role": "user", "content": raw_input}]
        elif isinstance(raw_input, list):
            text_parts, messages = [], []
            for item in raw_input:
                if isinstance(item, dict) and item.get("role") and "content" in item:
                    messages.append(item)
                elif isinstance(item, dict) and item.get("type") in ("text", "input_text"):
                    text_parts.append(str(item.get("text", "")))
                else:
                    text_parts.append(item if isinstance(item, str) else str(item))
            if text_parts and not messages:
                messages = [{"role": "user", "content": "".join(text_parts)}]
            if not messages:
                messages = [{"role": "user", "content": ""}]
        else:
            messages = [{"role": "user", "content": str(raw_input)}]
        chat_body = dict(data)
        chat_body["messages"] = messages
        chat_body["stream"] = False
        req = _build_request(chat_body)
        valid, error_msg = _validate_request(req)
        if not valid:
            return jsonify({"error": {"message": error_msg, "type": "invalid_request_error"}}), 400
        g.request_model = req.model
        try:
            provider, inference_target, temporary_provider = _resolve_inference_provider(data, req)
        except TargetingError as exc:
            return _target_error(exc)
        if not provider:
            return jsonify({"error": {
                "message": f"No enabled provider supports model '{req.model}'.",
                "type": "invalid_request_error",
                "code": "model_not_found",
            }}), 404
        g.selected_provider_id = provider.provider_id
        rate_response = enforce_provider_rate_limit(provider.provider_id)
        if rate_response is not None:
            return rate_response
        apply_feature_defaults(req, provider)
        drop_optional_tools_for_text_only_provider(req, provider)
        if not _try_acquire_provider_slot("responses", provider.provider_id):
            return _provider_busy_response("responses", provider.provider_id)
        try:
            translated_req = mcp_translator.translate_request(req, provider)
            session = _get_session(req)
            response = _run_async(provider.chat_completion(translated_req, session), timeout=240)
            normalized = _annotate_inference_target(mcp_normalizer.normalize_response(response, provider, translated_req), req)
            _finalize_usage_for_audit(req, normalized)
            text = "".join(c.message.content or "" for c in normalized.choices)
            return jsonify({
                "id": normalized.id,
                "object": "response",
                "created": normalized.created,
                "model": normalized.model,
                "output": [{
                    "type": "message",
                    "role": "assistant",
                    "content": [{"type": "output_text", "text": text}],
                }],
                "usage": {
                    "prompt_tokens": normalized.usage.prompt_tokens,
                    "completion_tokens": normalized.usage.completion_tokens,
                    "total_tokens": normalized.usage.total_tokens,
                },
                "provider_meta": normalized.provider_meta,
            })
        except Exception as e:
            logger.error(f"Responses error: {e}")
            error_resp = mcp_normalizer.normalize_error(e, provider)
            return jsonify(error_resp), _http_status_for_error(e)
        finally:
            _release_provider_slot("responses", provider.provider_id)
            if temporary_provider:
                try: _run_async(provider.close(), timeout=10)
                except Exception: logger.debug("Target responses provider cleanup failed", exc_info=True)

    def _stream_response(provider, req: ChatCompletionRequest, session, slot_kind: str, close_provider: bool = False):
        def generate():
            event_queue = queue.Queue()
            sentinel = object()
            completed = False

            async def produce():
                try:
                    async for chunk in provider.chat_completion_stream(req, session):
                        normalized = mcp_normalizer.normalize_chunk(chunk, provider)
                        normalized = _annotate_inference_target(normalized, req)
                        event_queue.put(("data", _format_stream_chunk(normalized)))
                    event_queue.put(("done", sentinel))
                except Exception as e:
                    event_queue.put(("error", e))

            future = asyncio.run_coroutine_threadsafe(produce(), _async_loop)
            try:
                while True:
                    try:
                        kind, payload = event_queue.get(timeout=2)
                    except queue.Empty:
                        # SSE keepalive makes client/Kilo disconnects observable
                        # even while the Web-chat provider is still thinking and
                        # has not emitted a model chunk yet.
                        yield ": keepalive\n\n"
                        continue
                    if kind == "data":
                        yield f"data: {json.dumps(payload)}\n\n"
                    elif kind == "done":
                        yield "data: [DONE]\n\n"
                        completed = True
                        break
                    elif kind == "error":
                        logger.error(f"Stream error: {payload}")
                        error_resp = mcp_normalizer.normalize_error(payload, provider)
                        yield f"data: {json.dumps(error_resp)}\n\n"
                        completed = True
                        break
            finally:
                # A disconnected client must not leave provider work running in
                # the persistent async loop or Web-chat upstream indefinitely.
                if not completed:
                    try:
                        cancel_future = asyncio.run_coroutine_threadsafe(
                            provider.cancel_active_generation("stream_client_disconnected"),
                            _async_loop,
                        )
                        cancel_result = cancel_future.result(timeout=5)
                        if isinstance(cancel_result, dict):
                            safe_cancel_result = {
                                k: v for k, v in cancel_result.items()
                                if k not in {"url", "label"}
                            }
                        else:
                            safe_cancel_result = cancel_result
                        logger.info(
                            "Provider active-generation cancel hook result for %s: %s",
                            getattr(provider, "provider_id", "unknown"),
                            safe_cancel_result,
                        )
                    except Exception as e:
                        logger.warning(
                            "Provider active-generation cancel hook failed for %s: %s",
                            getattr(provider, "provider_id", "unknown"),
                            e,
                        )
                if not future.done():
                    future.cancel()
                _release_provider_slot(slot_kind, provider.provider_id)
                if close_provider:
                    try:
                        close_future = asyncio.run_coroutine_threadsafe(provider.close(), _async_loop)
                        close_future.result(timeout=10)
                    except Exception:
                        logger.debug("Target stream provider cleanup failed", exc_info=True)

        return Response(stream_with_context(generate()), mimetype="text/event-stream")

    @app.route("/v1/chat/code", methods=["POST"])
    def code_chat():
        """
        Code Generation
        ---
        tags:
          - Chat
        summary: Generate code with automatic code block extraction
        parameters:
          - in: body
            name: body
            required: true
            schema:
              allOf:
                - $ref: '#/definitions/ChatCompletionRequest'
                - type: object
                  properties:
                    language:
                      type: string
                      example: python
                    code_only:
                      type: boolean
                      default: false
                    save_to:
                      type: string
                      example: /path/to/output.py
        responses:
          200:
            description: Code generation response
            schema:
              $ref: '#/definitions/CodeChatResponse'
          400:
            description: Invalid request
            schema:
              $ref: '#/definitions/Error'
          503:
            description: No provider available
            schema:
              $ref: '#/definitions/Error'
        """
        data = request.get_json(force=True)
        req = _build_request(data)

        valid, error_msg = _validate_request(req)
        if not valid:
            return jsonify({"error": {"message": error_msg, "type": "invalid_request_error"}}), 400

        g.request_model = req.model

        provider = provider_router.select_provider(
            model=req.model,
            require_tools=request_requires_tools(req),
        )
        if not provider:
            return jsonify({"error": {
                "message": f"No provider supports model '{req.model}' with the requested capabilities. If using Kilo Code with qwen/zai, tool schemas are only optional; required tool calls need chatgpt-web or a tool-capable provider.",
                "type": "invalid_request_error",
                "code": "unknown_or_unsupported_model",
                "details": {"requested_tools": bool(req.tools), "tool_choice": req.tool_choice},
            }}), 400

        g.selected_provider_id = provider.provider_id
        rate_response = enforce_provider_rate_limit(provider.provider_id)
        if rate_response is not None:
            return rate_response
        apply_feature_defaults(req, provider)
        drop_optional_tools_for_text_only_provider(req, provider)

        if not _try_acquire_provider_slot("code_chat", provider.provider_id):
            return _provider_busy_response("code_chat", provider.provider_id)

        try:
            translated_req = mcp_translator.translate_request(req, provider)
            response = _run_async(provider.chat_completion(translated_req), timeout=240)
            normalized = mcp_normalizer.normalize_response(response, provider, translated_req)
            _finalize_usage_for_audit(req, normalized)

            from core.code_parser import extract_code_blocks, save_code_block
            response_text = normalized.choices[0].message.content or ""
            blocks = extract_code_blocks(response_text, language=req.provider_options.get("language"))

            payload = _format_response(normalized, provider)
            payload["code"] = {
                "blocks": blocks,
                "language": req.provider_options.get("language"),
                "count": len(blocks),
            }

            if req.provider_options.get("code_only"):
                payload["choices"][0]["message"]["content"] = "\n".join(b["code"] for b in blocks)

            if req.provider_options.get("save_to") and blocks:
                try:
                    path = req.provider_options["save_to"]
                    saved = save_code_block(blocks[0]["code"], path)
                    payload["code"]["saved_to"] = saved
                except Exception as e:
                    logger.error(f"Save code failed: {e}")

            return jsonify(payload)
        except Exception as e:
            logger.error(f"Code chat error: {e}")
            error_resp = mcp_normalizer.normalize_error(e, provider)
            return jsonify(error_resp), _http_status_for_error(e)
        finally:
            _release_provider_slot("code_chat", provider.provider_id)

    def _interactive_agent_tools():
        cfg=(config.get("agent_tools") or {})
        roots=cfg.get("read_roots") or ([r"D:\\"] if os.name == "nt" else [str(Path.cwd())])
        return AgentToolRegistry(roots=roots, repo_root=Path.cwd())

    def _agent_tool_result_messages(tool_calls, registry, policy, seen, step):
        messages=[]; evidence=[]; duplicate_blocked=False
        for call in tool_calls or []:
            enforce_auth = bool((config.get("agent_tools") or {}).get("authorization_gate_enabled", True))
            message, record, duplicate = execute_tool_call(
                registry, call, policy, seen, step, enforce_authorization=enforce_auth
            )
            messages.append(message); evidence.append(record)
            duplicate_blocked = duplicate_blocked or duplicate
        return messages, evidence, duplicate_blocked

    @app.route("/v1/chat/conversation", methods=["POST"])
    def conversation_chat():
        """
        Conversation Chat
        ---
        tags:
          - Chat
        summary: Chat with conversation continuity
        parameters:
          - in: body
            name: body
            required: true
            schema:
              allOf:
                - $ref: '#/definitions/ChatCompletionRequest'
                - type: object
                  properties:
                    conversation_id:
                      type: string
                      example: conv-abc123
        responses:
          200:
            description: Conversation response
            schema:
              $ref: '#/definitions/ConversationResponse'
          400:
            description: Invalid request
            schema:
              $ref: '#/definitions/Error'
          503:
            description: No provider available
            schema:
              $ref: '#/definitions/Error'
        """
        try:
            data = _hydrate_upload_ids(request.get_json(force=True) or {})
        except UploadStoreError as exc:
            return jsonify({"error":{"message":str(exc),"type":"invalid_request_error","code":exc.code}}), exc.status
        req = _build_request(data)
        req.conversation_id = data.get("conversation_id") or uuid.uuid4().hex
        agent_mode = bool(data.get("agent_mode"))
        if agent_mode:
            req.stream = False
            req.tools = agent_tool_definitions()
            req.tool_choice = "auto"

        valid, error_msg = _validate_request(req)
        if not valid:
            return jsonify({"error": {"message": error_msg, "type": "invalid_request_error"}}), 400

        g.request_model = req.model

        try:
            provider, inference_target, temporary_provider = _resolve_inference_provider(data, req)
        except TargetingError as exc:
            return _target_error(exc)
        if not provider:
            return jsonify({"error": {
                "message": f"No provider supports model '{req.model}' with the requested capabilities. If using Kilo Code with qwen/zai, tool schemas are only optional; required tool calls need chatgpt-web or a tool-capable provider.",
                "type": "invalid_request_error",
                "code": "unknown_or_unsupported_model",
                "details": {"requested_tools": bool(req.tools), "tool_choice": req.tool_choice},
            }}), 400

        g.selected_provider_id = provider.provider_id
        apply_feature_defaults(req, provider)
        drop_optional_tools_for_text_only_provider(req, provider)
        try:
            media_state = validate_media_request(provider, data)
        except MediaContractError as exc:
            return jsonify({"error": {
                "message": str(exc), "type": "invalid_request_error", "code": exc.code,
                "provider": provider.provider_id, "details": exc.details,
            }}), 400
        req.provider_options = req.provider_options or {}
        req.provider_options["media_contract"] = media_state
        rate_response = enforce_provider_rate_limit(provider.provider_id)
        if rate_response is not None:
            return rate_response

        if not _try_acquire_provider_slot("conversation_chat", provider.provider_id):
            return _provider_busy_response("conversation_chat", provider.provider_id)

        try:
            translated_req = mcp_translator.translate_request(req, provider)
            session = _get_session(req, provider=provider, create=True)

            if req.stream:
                return _stream_response(provider, translated_req, session, "conversation_chat", close_provider=temporary_provider)
            else:
                response = _run_async(provider.chat_completion(translated_req, session), timeout=240)
                normalized = _annotate_inference_target(mcp_normalizer.normalize_response(response, provider, translated_req), req)
                if agent_mode:
                    registry = _interactive_agent_tools()
                    policy = AgentLoopPolicy.from_config(config.get("agent_tools"))
                    loop_started = time.monotonic()
                    seen_calls = {}
                    agent_evidence = []
                    terminal_state = "completed"
                    steps = 0
                    for _step in range(policy.max_steps):
                        msg = normalized.choices[0].message
                        if not msg.tool_calls:
                            terminal_state = "completed"
                            break
                        steps = _step + 1
                        remaining = remaining_loop_seconds(loop_started, policy)
                        if remaining <= 0:
                            terminal_state = "timeout_budget_exhausted"
                            break
                        req.messages.append({"role":"assistant","content":msg.content or "","tool_calls":msg.tool_calls})
                        tool_messages, records, duplicate_blocked = _agent_tool_result_messages(
                            msg.tool_calls, registry, policy, seen_calls, steps
                        )
                        req.messages.extend(tool_messages)
                        agent_evidence.extend(records)
                        if duplicate_blocked:
                            terminal_state = "duplicate_call_blocked"
                            break
                        translated_req = mcp_translator.translate_request(req, provider)
                        remaining = remaining_loop_seconds(loop_started, policy)
                        if remaining <= 0:
                            terminal_state = "timeout_budget_exhausted"
                            break
                        response = _run_async(
                            provider.chat_completion(translated_req, session),
                            timeout=min(240, max(1.0, remaining)),
                        )
                        normalized = mcp_normalizer.normalize_response(response, provider, translated_req)
                    else:
                        if normalized.choices[0].message.tool_calls:
                            terminal_state = "max_steps_exhausted"
                    normalized.provider_meta = normalized.provider_meta or {}
                    normalized.provider_meta["agent_mode"] = True
                    normalized.provider_meta["agent_tools"] = [x["function"]["name"] for x in agent_tool_definitions()]
                    normalized.provider_meta["agent_evidence"] = agent_evidence
                    normalized.provider_meta["agent_terminal"] = summarize_terminal_state(
                        terminal_state, steps, agent_evidence, loop_started
                    )
                _finalize_usage_for_audit(req, normalized)

                if normalized.provider_meta.get("conversation_id"):
                    mcp_session_manager.update_provider_session_id(
                        req.conversation_id,
                        normalized.provider_meta["conversation_id"]
                    )

                payload = _format_response(normalized, provider)
                payload["conversation_id"] = req.conversation_id

                return jsonify(payload)
        except Exception as e:
            logger.error(f"Conversation chat error: {e}")
            error_resp = mcp_normalizer.normalize_error(e, provider)
            return jsonify(error_resp), _http_status_for_error(e)
        finally:
            if not req.stream:
                _release_provider_slot("conversation_chat", provider.provider_id)
                if temporary_provider:
                    try: _run_async(provider.close(), timeout=10)
                    except Exception: logger.debug("Target conversation provider cleanup failed", exc_info=True)

    return app


app = create_app()

if __name__ == "__main__":
    config = load_config(DEFAULT_CONFIG_PATH)
    server_config = config["server"]
    http_threads = int(
        os.getenv(
            "HOOSHKA_GW_HTTP_THREADS",
            str(server_config.get("threads", 12)),
        )
    )
    http_threads = max(4, http_threads)
    from waitress import serve

    serve(
        app,
        host=server_config["host"],
        port=server_config["port"],
        threads=http_threads,
    )

