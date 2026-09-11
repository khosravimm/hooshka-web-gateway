from typing import AsyncIterator, Optional

from adapters.deepseek_browser_transport import DeepSeekBrowserUITransport
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
from core.tool_protocol import serialize_messages, parse_tool_envelope, strong_auto_tool_signal


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


class DeepSeekWebProvider(Provider):
    """DeepSeek Web Chat provider using the controlled browser UI session."""

    def __init__(self, config: ProviderConfig):
        super().__init__(config)
        c = config.config
        self._require_authenticated = bool(c.get("require_authenticated", True))
        self._browser = DeepSeekBrowserUITransport(
            self.provider_id,
            cdp_url=c.get("cdp_url", "http://127.0.0.1:9223"),
            base_url=c.get("base_url", "https://chat.deepseek.com/"),
            launch_timeout=float(c.get("launch_timeout", 45)),
            first_event_timeout=float(c.get("first_event_timeout", 45)),
            idle_timeout=float(c.get("idle_timeout", 90)),
            total_timeout=float(c.get("total_timeout", 180)),
            poll_interval=float(c.get("poll_interval", 0.5)),
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
            max_context_tokens=128_000,
            supported_models=["deepseek-web"],
            search=False,
            reasoning=True,
            files=False,
            transport_mode="browser_ui",
        )

    def supports_model(self, model: str) -> bool:
        return model == "deepseek-web" or model.startswith("deepseek:")

    async def _require_authenticated_session(self) -> None:
        if not self._require_authenticated:
            return
        status = await self._browser.session_status()
        if not status.get("authenticated"):
            raise ProviderError(
                "DeepSeek Web Chat requires an authenticated browser session",
                "auth_required",
                self.provider_id,
                {"session_mode": status.get("mode"), "signals": status.get("signals")},
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
            return serialize_messages(request.messages, tools=request.tools, tool_choice=request.tool_choice)
        parts = []
        for message in request.messages:
            content = message.get("content") or ""
            if content:
                parts.append(str(content))
        return "\n\n".join(parts).strip()

    async def health_check(self) -> bool:
        try:
            await self._require_authenticated_session()
            return await self._browser.health()
        except Exception:
            return False

    async def list_models(self) -> list[ModelInfo]:
        return [ModelInfo(id="deepseek-web", owned_by="deepseek-web", provider=self.provider_id)]

    async def _run_text(self, request: ChatCompletionRequest) -> tuple[str, Optional[list], str]:
        await self._require_authenticated_session()
        pieces = []
        conversation_id = ""
        async for event in self._browser.stream_text(self._request_text(request), new_chat=True):
            pieces.append(event.get("text") or "")
            conversation_id = event.get("conversation_id") or conversation_id
        response_text = "".join(pieces)
        content = response_text
        tool_calls = None
        finish_reason = "stop"
        if request.tools:
            content, tool_calls, valid_protocol = parse_tool_envelope(response_text)
            must_call = _tool_required(request.tool_choice)
            if not valid_protocol or (must_call and not tool_calls):
                raise ProviderError(
                    "DeepSeek Web Chat failed the required tool protocol",
                    "tool_protocol_violation",
                    self.provider_id,
                    {"must_call": must_call, "response_preview": response_text[:500]},
                )
            if request.tool_choice in (None, "auto") and not tool_calls and not self._has_tool_result(request):
                signal = strong_auto_tool_signal(content or response_text, request.tools, self._latest_user_text(request))
                if signal:
                    raise ProviderError(
                        "DeepSeek Web Chat returned prose when tool use looked required",
                        "tool_protocol_violation",
                        self.provider_id,
                        {"signal": signal, "response_preview": response_text[:500]},
                    )
            if tool_calls:
                finish_reason = "tool_calls"
        return content, tool_calls, finish_reason

    async def chat_completion(
        self,
        request: ChatCompletionRequest,
        session: Optional[SessionContext] = None,
    ) -> ChatCompletionResponse:
        if not self.supports_model(request.model):
            raise ProviderError("Unsupported DeepSeek Web model", "invalid_model", self.provider_id)
        content, tool_calls, finish_reason = await self._run_text(request)
        return ChatCompletionResponse(
            id=self._generate_id(),
            created=self._current_timestamp(),
            model=request.model,
            choices=[Choice(index=0, message=Message(role="assistant", content=content, tool_calls=tool_calls), finish_reason=finish_reason)],
            usage=Usage(),
            provider_meta={
                "provider": self.provider_id,
                "transport_mode": "browser_ui",
                "streaming_mode": "reconstructed",
                "conversation_id": self._browser.last_conversation_url,
                "block_signals": dict(self._browser.last_block_signals or {}),
            },
        )

    async def chat_completion_stream(
        self,
        request: ChatCompletionRequest,
        session: Optional[SessionContext] = None,
    ) -> AsyncIterator[ChatCompletionChunk]:
        if not self.supports_model(request.model):
            raise ProviderError("Unsupported DeepSeek Web model", "invalid_model", self.provider_id)
        content, tool_calls, finish_reason = await self._run_text(request)
        chunk_id = self._generate_id()
        if tool_calls:
            yield ChatCompletionChunk(
                id=chunk_id,
                created=self._current_timestamp(),
                model=request.model,
                choices=[ChunkChoice(index=0, delta=Delta(tool_calls=tool_calls), finish_reason=finish_reason)],
                provider_meta={"provider": self.provider_id, "transport_mode": "browser_ui"},
            )
        else:
            yield ChatCompletionChunk(
                id=chunk_id,
                created=self._current_timestamp(),
                model=request.model,
                choices=[ChunkChoice(index=0, delta=Delta(content=content), finish_reason=None)],
                provider_meta={"provider": self.provider_id, "transport_mode": "browser_ui"},
            )
            yield ChatCompletionChunk(
                id=chunk_id,
                created=self._current_timestamp(),
                model=request.model,
                choices=[ChunkChoice(index=0, delta=Delta(), finish_reason=finish_reason)],
                provider_meta={"provider": self.provider_id, "transport_mode": "browser_ui"},
            )

    async def close(self) -> None:
        await self._browser.close()


def create_deepseek_web_provider(
    provider_id: str = "deepseek-web",
    priority: int = 70,
    **config,
) -> DeepSeekWebProvider:
    return DeepSeekWebProvider(
        ProviderConfig(
            provider_id=provider_id,
            provider_type=ProviderType.DEEPSEEK_WEB,
            enabled=True,
            priority=priority,
            config=config,
            capabilities=ProviderCapabilities(
                chat_completion=True,
                streaming=True,
                streaming_mode="reconstructed",
                tools=True,
                vision=False,
                embeddings=False,
                max_context_tokens=128_000,
                supported_models=["deepseek-web"],
                search=False,
                reasoning=True,
                files=False,
                transport_mode="browser_ui",
            ),
        )
    )
