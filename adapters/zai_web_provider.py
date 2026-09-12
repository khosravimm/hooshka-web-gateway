import re
from typing import AsyncIterator, Optional

from adapters.zai_browser_transport import ZaiBrowserControllerTransport
from core.browser_observability import BrowserEvidenceMismatch, BrowserModelEvidence
from core.tool_protocol import serialize_messages, parse_tool_envelope, strong_auto_tool_signal
from core.providers import (
    Provider,
    ProviderCapabilities,
    ProviderConfig,
    ProviderError,
    ProviderType,
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChatCompletionChunk,
    Choice,
    Message,
    Usage,
    ChunkChoice,
    Delta,
    ModelInfo,
    SessionContext,
)


def _tool_required(tool_choice) -> bool:
    if tool_choice is None:
        return False
    if isinstance(tool_choice, str):
        return tool_choice not in {"auto", "none"}
    if isinstance(tool_choice, dict):
        if str(tool_choice.get("type", "")).lower() in {"function", "tool", "required"}:
            return True
        return "function" in tool_choice or "tool" in tool_choice
    return False


def _explicit_tool_hint(request: ChatCompletionRequest) -> Optional[dict]:
    if request.tool_choice not in (None, "auto"):
        return None
    if any(message.get("role") == "tool" for message in request.messages or []):
        return None
    latest = ""
    for message in reversed(request.messages or []):
        if message.get("role") == "user":
            latest = str(message.get("content") or "")
            break
    if not latest:
        return None
    offered = []
    for tool in request.tools or []:
        name = (((tool or {}).get("function") or {}).get("name") or "").strip()
        if name:
            offered.append(name)
    matches = []
    for name in offered:
        patterns = [
            rf"\buse\s+(?:the\s+)?{re.escape(name)}\s+tool\b",
            rf"\buse\s+{re.escape(name)}\b",
            rf"\b{re.escape(name)}\s+tool\b",
        ]
        if any(re.search(pattern, latest, re.I) for pattern in patterns):
            matches.append(name)
    if len(matches) != 1:
        return None
    return {"type": "function", "function": {"name": matches[0]}}


class ZaiWebProvider(Provider):
    def _verify_browser_model_evidence(self, request: ChatCompletionRequest, upstream_model: str, response_model: Optional[str] = None) -> dict:
        evidence = BrowserModelEvidence(
            provider=self.provider_id,
            requested_model=request.model,
            expected_upstream_model=upstream_model,
            frontend_version=getattr(self._browser, "frontend_version", None),
            ui_selected_model=getattr(self._browser, "last_selected_model_label", None),
            backend_request_model=getattr(self._browser, "last_backend_request_model", None),
            response_model=response_model,
        )
        try:
            return evidence.validate(require_selection=True, require_backend=True)
        except BrowserEvidenceMismatch as exc:
            raise ProviderError(
                "Z.ai browser model evidence mismatch",
                "model_evidence_mismatch",
                self.provider_id,
                exc.details,
            ) from exc

    def __init__(self, config: ProviderConfig):
        super().__init__(config)
        c = config.config
        self._default_upstream_model = c.get("default_upstream_model", "glm-5.3")
        self._require_authenticated = bool(c.get("require_authenticated", True))
        self._browser = ZaiBrowserControllerTransport(
            self.provider_id,
            cdp_url=c.get("cdp_url", "http://127.0.0.1:9223"),
            base_url=c.get("base_url", "https://chat.z.ai/"),
            launch_timeout=float(c.get("launch_timeout", 30)),
            first_event_timeout=float(c.get("first_event_timeout", 45)),
            idle_timeout=float(c.get("idle_timeout", 60)),
            total_timeout=float(c.get("total_timeout", 180)),
            poll_interval=float(c.get("poll_interval", 0.10)),
        )

    @property
    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            chat_completion=True,
            streaming=True,
            streaming_mode="reconstructed",
            tools=True,
            vision=False,
            embeddings=False,
            max_context_tokens=200_000,
            supported_models=["zai-web"],
            search=False,
            reasoning=True,
            files=False,
            transport_mode="browser_backend_controller",
        )

    @staticmethod
    def _has_tool_result(request: ChatCompletionRequest) -> bool:
        return any(message.get("role") == "tool" for message in request.messages or [])

    @staticmethod
    def _latest_user_text(request: ChatCompletionRequest) -> str:
        for message in reversed(request.messages or []):
            if message.get("role") == "user":
                return str(message.get("content") or "")
        return ""

    @staticmethod
    def _request_text(request: ChatCompletionRequest) -> str:
        if request.tools or any(m.get("role") != "user" for m in request.messages):
            instruction_choice = _explicit_tool_hint(request) or request.tool_choice
            return serialize_messages(request.messages, tools=request.tools, tool_choice=instruction_choice)
        parts = []
        for message in request.messages:
            content = message.get("content") or ""
            if content:
                parts.append(str(content))
        return "\n\n".join(parts).strip()

    async def _require_authenticated_session(self) -> None:
        if not self._require_authenticated:
            return
        status = await self._browser.session_status()
        if not status.get("authenticated"):
            raise ProviderError(
                "Z.ai Web requires an authenticated browser session; guest mode is disabled by policy",
                "auth_required",
                self.provider_id,
                {"session_mode": "guest_disabled"},
            )

    async def health_check(self) -> bool:
        try:
            await self._require_authenticated_session()
            return await self._browser.health()
        except ProviderError:
            return False

    async def list_models(self) -> list[ModelInfo]:
        models = [ModelInfo(id="zai-web", owned_by="z-ai-web", provider=self.provider_id)]
        if self._require_authenticated:
            status = await self._browser.session_status()
            if not status.get("authenticated"):
                return models
        upstream_ids = await self._browser.model_ids()
        seen = {"zai-web"}
        for mid in upstream_ids:
            model_id = f"zai:{mid}"
            if model_id in seen:
                continue
            models.append(ModelInfo(id=model_id, owned_by="z-ai-web", provider=self.provider_id))
            seen.add(model_id)
        return models

    def supports_model(self, model: str) -> bool:
        return model == "zai-web" or model.startswith("zai:")

    def _resolve_upstream_model(self, request: ChatCompletionRequest) -> str:
        if request.model == "zai-web":
            return (request.provider_options or {}).get("upstream_model") or self._default_upstream_model
        if request.model.startswith("zai:"):
            return request.model.split(":", 1)[1]
        raise ProviderError("Unsupported Z.ai model", "invalid_model", self.provider_id)

    async def _resolve_and_validate_upstream_model(self, request: ChatCompletionRequest) -> str:
        await self._require_authenticated_session()
        upstream_model = self._resolve_upstream_model(request)
        available = await self._browser.model_ids()
        if upstream_model not in available:
            raise ProviderError(
                "Requested Z.ai model is not available in the current session",
                "invalid_model",
                self.provider_id,
                {"model": upstream_model},
            )
        return upstream_model

    async def _run_text(self, request: ChatCompletionRequest) -> tuple[Optional[str], Optional[list], str, str, str, str, dict]:
        pieces = []
        chat_id = ""
        requested_upstream_model = await self._resolve_and_validate_upstream_model(request)
        upstream_model = ""
        async for event in self._browser.stream_text(
            self._request_text(request),
            upstream_model=requested_upstream_model,
        ):
            if event.get("type") == "text_delta":
                pieces.append(event.get("text") or "")
            chat_id = event.get("chat_id") or chat_id
            upstream_model = event.get("model") or upstream_model

        model_evidence = self._verify_browser_model_evidence(
            request,
            requested_upstream_model,
            upstream_model or None,
        )

        response_text = "".join(pieces)
        content: Optional[str] = response_text
        tool_calls = None
        finish_reason = "stop"
        if request.tools:
            content, tool_calls, valid_protocol = parse_tool_envelope(response_text)
            must_call = _tool_required(request.tool_choice)
            has_tool_result = self._has_tool_result(request)
            looks_like_tool_request = '"tool_calls"' in response_text or "'tool_calls'" in response_text or "DSML" in response_text
            raw_final_after_tool = has_tool_result and not must_call and not tool_calls and not looks_like_tool_request
            if (not valid_protocol and not raw_final_after_tool) or (must_call and not tool_calls):
                raise ProviderError(
                    "Z.ai Web Chat failed the required tool protocol",
                    "tool_protocol_violation",
                    self.provider_id,
                    {"must_call": must_call, "has_tool_result": has_tool_result, "response_preview": response_text[:500]},
                )
            if raw_final_after_tool and not valid_protocol:
                content = response_text
            if request.tool_choice in (None, "auto") and not tool_calls and not has_tool_result:
                signal = strong_auto_tool_signal(content or response_text, request.tools, self._latest_user_text(request))
                if signal:
                    raise ProviderError(
                        "Z.ai Web Chat returned prose when tool use looked required",
                        "tool_protocol_violation",
                        self.provider_id,
                        {"signal": signal, "response_preview": response_text[:500]},
                    )
            if tool_calls:
                finish_reason = "tool_calls"
        return content, tool_calls, finish_reason, chat_id, requested_upstream_model, upstream_model, model_evidence

    async def chat_completion(
        self,
        request: ChatCompletionRequest,
        session: Optional[SessionContext] = None,
    ) -> ChatCompletionResponse:
        if not self.supports_model(request.model):
            raise ProviderError("Unsupported Z.ai model", "invalid_model", self.provider_id)
        if (request.provider_options or {}).get("search"):
            raise ProviderError("Z.ai search is not enabled until E2 validation passes", "unsupported_search", self.provider_id)

        content, tool_calls, finish_reason, chat_id, requested_upstream_model, upstream_model, model_evidence = await self._run_text(request)

        return ChatCompletionResponse(
            id=self._generate_id(),
            created=self._current_timestamp(),
            model=request.model,
            choices=[Choice(index=0, message=Message(role="assistant", content=content, tool_calls=tool_calls), finish_reason=finish_reason)],
            usage=Usage(),
            provider_meta={
                "provider": self.provider_id,
                "transport_mode": "browser_backend_controller",
                "streaming_mode": "reconstructed",
                "frontend_version": self._browser.frontend_version,
                "session_mode": self._browser.last_session_mode,
                "conversation_id": chat_id or None,
                "requested_upstream_model": requested_upstream_model,
                "upstream_model": upstream_model or requested_upstream_model or None,
                "selected_model_label": getattr(self._browser, "last_selected_model_label", None),
                "backend_request_model": getattr(self._browser, "last_backend_request_model", None),
                "model_evidence": model_evidence,
                "browser_observability": {
                    "backend_response_status": getattr(self._browser, "last_backend_response_status", None),
                    "backend_response_content_type": getattr(self._browser, "last_backend_response_content_type", None),
                    "backend_lifecycle": list(getattr(self._browser, "backend_lifecycle", [])[-8:]),
                },
            },
        )

    async def chat_completion_stream(
        self,
        request: ChatCompletionRequest,
        session: Optional[SessionContext] = None,
    ) -> AsyncIterator[ChatCompletionChunk]:
        if not self.supports_model(request.model):
            raise ProviderError("Unsupported Z.ai model", "invalid_model", self.provider_id)
        if (request.provider_options or {}).get("search"):
            raise ProviderError("Z.ai search is not enabled until E2 validation passes", "unsupported_search", self.provider_id)

        if request.tools:
            content, tool_calls, finish_reason, chat_id, requested_upstream_model, upstream_model, model_evidence = await self._run_text(request)
            chunk_id = self._generate_id()
            if tool_calls:
                yield ChatCompletionChunk(
                    id=chunk_id,
                    created=self._current_timestamp(),
                    model=request.model,
                    choices=[ChunkChoice(index=0, delta=Delta(tool_calls=tool_calls), finish_reason=finish_reason)],
                    provider_meta={
                        "provider": self.provider_id,
                        "transport_mode": "browser_backend_controller",
                        "streaming_mode": "reconstructed",
                        "conversation_id": chat_id or None,
                        "requested_upstream_model": requested_upstream_model,
                        "upstream_model": upstream_model or requested_upstream_model or None,
                        "model_evidence": model_evidence,
                    },
                )
            else:
                yield ChatCompletionChunk(
                    id=chunk_id,
                    created=self._current_timestamp(),
                    model=request.model,
                    choices=[ChunkChoice(index=0, delta=Delta(content=content or ""), finish_reason=None)],
                    provider_meta={"provider": self.provider_id, "transport_mode": "browser_backend_controller"},
                )
                yield ChatCompletionChunk(
                    id=chunk_id,
                    created=self._current_timestamp(),
                    model=request.model,
                    choices=[ChunkChoice(index=0, delta=Delta(), finish_reason=finish_reason)],
                    provider_meta={"provider": self.provider_id, "transport_mode": "browser_backend_controller"},
                )
            return

        chunk_id = self._generate_id()
        requested_upstream_model = await self._resolve_and_validate_upstream_model(request)
        meta = {
            "provider": self.provider_id,
            "transport_mode": "browser_backend_controller",
            "streaming_mode": "reconstructed",
            "frontend_version": self._browser.frontend_version,
            "session_mode": self._browser.last_session_mode,
            "conversation_id": None,
            "requested_upstream_model": requested_upstream_model,
            "upstream_model": requested_upstream_model,
            "selected_model_label": getattr(self._browser, "last_selected_model_label", None),
            "backend_request_model": getattr(self._browser, "last_backend_request_model", None),
        }
        async for event in self._browser.stream_text(
            self._request_text(request),
            upstream_model=requested_upstream_model,
        ):
            meta["conversation_id"] = event.get("chat_id") or meta["conversation_id"]
            meta["upstream_model"] = event.get("model") or meta["upstream_model"]
            meta["selected_model_label"] = getattr(self._browser, "last_selected_model_label", None)
            meta["backend_request_model"] = getattr(self._browser, "last_backend_request_model", None)
            meta["requested_upstream_model"] = requested_upstream_model
            if event.get("type") == "text_delta":
                yield ChatCompletionChunk(
                    id=chunk_id,
                    created=self._current_timestamp(),
                    model=request.model,
                    choices=[ChunkChoice(index=0, delta=Delta(content=event.get("text") or ""), finish_reason=None)],
                    provider_meta=dict(meta),
                )
        meta["model_evidence"] = self._verify_browser_model_evidence(
            request,
            requested_upstream_model,
            meta.get("upstream_model"),
        )
        meta["browser_observability"] = {
            "backend_response_status": getattr(self._browser, "last_backend_response_status", None),
            "backend_response_content_type": getattr(self._browser, "last_backend_response_content_type", None),
            "backend_lifecycle": list(getattr(self._browser, "backend_lifecycle", [])[-8:]),
        }
        yield ChatCompletionChunk(
            id=chunk_id,
            created=self._current_timestamp(),
            model=request.model,
            choices=[ChunkChoice(index=0, delta=Delta(), finish_reason="stop")],
            provider_meta=dict(meta),
        )

    async def close(self) -> None:
        await self._browser.close()


def create_zai_web_provider(
    provider_id: str = "zai-web",
    priority: int = 95,
    **config_values,
) -> ZaiWebProvider:
    config = ProviderConfig(
        provider_id=provider_id,
        provider_type=ProviderType.ZAI_WEB,
        enabled=True,
        priority=priority,
        config=config_values,
        capabilities=ProviderCapabilities(
            chat_completion=True,
            streaming=True,
            streaming_mode="reconstructed",
            tools=True,
            vision=False,
            embeddings=False,
            max_context_tokens=200_000,
            supported_models=["zai-web"],
            search=False,
            reasoning=True,
            files=False,
            transport_mode="browser_backend_controller",
        ),
    )
    return ZaiWebProvider(config)
