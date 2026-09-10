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
from flask import Flask, request, jsonify, Response, stream_with_context, g
from flasgger import Swagger
from core.providers import (
    ProviderConfig,
    ProviderType,
    ProviderCapabilities,
    ChatCompletionRequest,
    SessionContext,
)
from core.provider_registry import provider_registry, provider_router
from core.mcp import mcp_translator, mcp_normalizer, mcp_session_manager
from core.governance import init_governance, auth_manager, rate_limiter
from core.config import load_config
from adapters.chatgpt_web_provider import create_chatgpt_web_provider
from adapters.qwen_web_provider import create_qwen_web_provider
from adapters.zai_web_provider import create_zai_web_provider
from control_panel import control_panel_bp


SWAGGER_TEMPLATE = {
    "swagger": "2.0",
    "info": {
        "title": "Hooshka Web Gateway API",
        "description": "Hooshka Web Gateway exposes one governed OpenAI-compatible local API for supported Web-chat providers. Provider-specific browser/session/transport behavior remains behind exact fail-closed routing.",
        "version": "0.6.5",
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
                "file_paths": {"type": "array", "items": {"type": "string"}, "example": ["/path/to/file.txt"]},
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


def create_app(config_path: str = "config.yaml") -> Flask:
    config = load_config(config_path)
    
    app = Flask(__name__)
    
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
    
    init_governance(app, config["governance"])
    
    for provider_config in config["providers"]:
        if not provider_config.get("enabled", True):
            continue
        
        pconfig = ProviderConfig(
            provider_id=provider_config["id"],
            provider_type=ProviderType(provider_config["type"]),
            enabled=provider_config.get("enabled", True),
            priority=provider_config.get("priority", 100),
            config=provider_config.get("config", {}),
            capabilities=ProviderCapabilities(**provider_config.get("capabilities", {})),
        )
        
        if pconfig.provider_type == ProviderType.CHATGPT_WEB:
            provider = create_chatgpt_web_provider(
                provider_id=pconfig.provider_id,
                adapter=pconfig.config.get("adapter", "dom"),
                cdp_url=pconfig.config.get("cdp_url", "http://127.0.0.1:9224"),
                chatgpt_url=pconfig.config.get("chatgpt_url", "https://chatgpt.com"),
                priority=pconfig.priority,
            )
            provider_registry.register(provider)
            rate_limiter.set_rate(pconfig.provider_id, pconfig.config.get("requests_per_minute", 20))
        elif pconfig.provider_type == ProviderType.QWEN_WEB:
            provider = create_qwen_web_provider(
                provider_id=pconfig.provider_id,
                priority=pconfig.priority,
                **pconfig.config,
            )
            provider_registry.register(provider)
            rate_limiter.set_rate(pconfig.provider_id, pconfig.config.get("requests_per_minute", 12))
        elif pconfig.provider_type == ProviderType.ZAI_WEB:
            provider = create_zai_web_provider(
                provider_id=pconfig.provider_id,
                priority=pconfig.priority,
                **pconfig.config,
            )
            provider_registry.register(provider)
            rate_limiter.set_rate(pconfig.provider_id, pconfig.config.get("requests_per_minute", 6))
    
    server_config = config["server"]
    
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
            model=data.get("model", "chatgpt-web"),
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
                "thinking": data.get("thinking", True),
                "search": data.get("search", False),
                "upstream_model": data.get("upstream_model"),
            },
        )
    
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
    
    def _get_session(req: ChatCompletionRequest) -> SessionContext | None:
        if not req.conversation_id:
            return None
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

    def _run_async(coro):
        future = asyncio.run_coroutine_threadsafe(coro, _async_loop)
        try:
            return future.result()
        except FutureTimeoutError:
            future.cancel()
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
        return jsonify({"status": "ok", "service": "hooshka-web-gateway", "legacy_service": "mcp-web-bridge"})

    @app.route("/ready", methods=["GET"])
    def ready():
        """Readiness check for at least one usable provider runtime."""
        providers = provider_registry.list_providers()
        details = []
        ready_any = False
        for provider in providers:
            try:
                ok = bool(_run_async(provider.health_check()))
            except Exception as e:
                ok = False
                logger.warning(f"Readiness check failed for {provider.provider_id}: {e}")
            details.append({"provider": provider.provider_id, "ready": ok})
            ready_any = ready_any or ok
        return jsonify({"status": "ready" if ready_any else "not_ready", "providers": details}), (200 if ready_any else 503)

    @app.route("/health/deep", methods=["GET"])
    def deep_health():
        """Alias for readiness, kept explicit for operational tooling."""
        return ready()
    
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
            "providers": [
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
                        "transport_mode": p.capabilities.transport_mode,
                    },
                }
                for p in providers
            ],
            "default": provider_registry.get_default().provider_id if provider_registry.get_default() else None,
        })
    
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
            try:
                models = _run_async(provider.list_models())
                all_models.extend(models)
            except Exception as e:
                logger.error(f"Failed to list models from {provider.provider_id}: {e}")
        
        return jsonify({
            "object": "list",
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
        data = request.get_json(force=True)
        req = _build_request(data)
        
        valid, error_msg = _validate_request(req)
        if not valid:
            return jsonify({"error": {"message": error_msg, "type": "invalid_request_error"}}), 400
        
        g.request_model = req.model
        
        provider_id = data.get("provider")
        if provider_id and provider_registry.get(provider_id) is None:
            return jsonify({"error": {
                "message": f"Unknown provider: {provider_id}",
                "type": "invalid_request_error",
                "code": "unknown_provider",
            }}), 400
        provider = provider_router.select_provider(
            model=req.model,
            provider_id=provider_id,
            require_streaming=req.stream,
            require_tools=bool(req.tools),
        )
        
        if not provider:
            return jsonify({"error": {
                "message": f"No provider supports model '{req.model}' with the requested capabilities",
                "type": "invalid_request_error",
                "code": "unknown_or_unsupported_model",
            }}), 400
        
        g.selected_provider_id = provider.provider_id
        
        try:
            translated_req = mcp_translator.translate_request(req, provider)
            session = _get_session(req)
            
            if req.stream:
                return _stream_response(provider, translated_req, session)
            else:
                response = _run_async(provider.chat_completion(translated_req, session))
                normalized = mcp_normalizer.normalize_response(response, provider)
                
                if session and normalized.provider_meta.get("conversation_id"):
                    mcp_session_manager.update_provider_session_id(
                        req.conversation_id,
                        normalized.provider_meta["conversation_id"]
                    )
                
                g.prompt_tokens = normalized.usage.prompt_tokens
                g.completion_tokens = normalized.usage.completion_tokens
                g.total_tokens = normalized.usage.total_tokens
                
                return jsonify(_format_response(normalized, provider))
        except Exception as e:
            logger.error(f"Chat completion error: {e}")
            error_resp = mcp_normalizer.normalize_error(e, provider)
            return jsonify(error_resp), 500
    
    def _stream_response(provider, req: ChatCompletionRequest, session):
        def generate():
            event_queue = queue.Queue()
            sentinel = object()

            async def produce():
                try:
                    async for chunk in provider.chat_completion_stream(req, session):
                        normalized = mcp_normalizer.normalize_chunk(chunk, provider)
                        event_queue.put(("data", _format_stream_chunk(normalized)))
                    event_queue.put(("done", sentinel))
                except Exception as e:
                    event_queue.put(("error", e))

            future = asyncio.run_coroutine_threadsafe(produce(), _async_loop)
            try:
                while True:
                    kind, payload = event_queue.get()
                    if kind == "data":
                        yield f"data: {json.dumps(payload)}\n\n"
                    elif kind == "done":
                        yield "data: [DONE]\n\n"
                        break
                    elif kind == "error":
                        logger.error(f"Stream error: {payload}")
                        error_resp = mcp_normalizer.normalize_error(payload, provider)
                        yield f"data: {json.dumps(error_resp)}\n\n"
                        break
            finally:
                # A disconnected client must not leave provider work running in
                # the persistent async loop indefinitely.
                if not future.done():
                    future.cancel()
        
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
            require_tools=bool(req.tools),
        )
        if not provider:
            return jsonify({"error": {
                "message": f"No provider supports model '{req.model}' with the requested capabilities",
                "type": "invalid_request_error",
                "code": "unknown_or_unsupported_model",
            }}), 400
        
        g.selected_provider_id = provider.provider_id
        
        try:
            translated_req = mcp_translator.translate_request(req, provider)
            response = _run_async(provider.chat_completion(translated_req))
            normalized = mcp_normalizer.normalize_response(response, provider)
            
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
            return jsonify(error_resp), 500
    
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
        data = request.get_json(force=True)
        req = _build_request(data)
        req.conversation_id = data.get("conversation_id") or uuid.uuid4().hex
        
        valid, error_msg = _validate_request(req)
        if not valid:
            return jsonify({"error": {"message": error_msg, "type": "invalid_request_error"}}), 400
        
        g.request_model = req.model
        
        provider = provider_router.select_provider(
            model=req.model,
            require_streaming=req.stream,
            require_tools=bool(req.tools),
        )
        if not provider:
            return jsonify({"error": {
                "message": f"No provider supports model '{req.model}' with the requested capabilities",
                "type": "invalid_request_error",
                "code": "unknown_or_unsupported_model",
            }}), 400
        
        g.selected_provider_id = provider.provider_id
        
        try:
            translated_req = mcp_translator.translate_request(req, provider)
            session = _get_session(req)
            
            if req.stream:
                return _stream_response(provider, translated_req, session)
            else:
                response = _run_async(provider.chat_completion(translated_req, session))
                normalized = mcp_normalizer.normalize_response(response, provider)
                
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
            return jsonify(error_resp), 500
    
    return app


app = create_app()

if __name__ == "__main__":
    config = load_config()
    server_config = config["server"]
    from waitress import serve

    serve(
        app,
        host=server_config["host"],
        port=server_config["port"],
        threads=4,
    )
