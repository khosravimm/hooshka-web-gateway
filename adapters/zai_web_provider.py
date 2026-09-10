from typing import AsyncIterator, Optional

from adapters.zai_browser_transport import ZaiBrowserControllerTransport
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


class ZaiWebProvider(Provider):
    def __init__(self, config: ProviderConfig):
        super().__init__(config)
        c = config.config
        self._default_upstream_model = c.get("default_upstream_model", "glm-5.3")
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
            tools=False,
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
    def _request_text(request: ChatCompletionRequest) -> str:
        parts = []
        for message in request.messages:
            role = message.get("role", "user")
            content = message.get("content") or ""
            if role == "system":
                parts.append(f"System: {content}")
            elif role == "user":
                parts.append(content)
            elif role == "assistant":
                parts.append(f"Assistant: {content}")
            elif role == "tool":
                parts.append(f"Tool result: {content}")
        return "\n\n".join(p for p in parts if p).strip()

    async def health_check(self) -> bool:
        return await self._browser.health()

    async def list_models(self) -> list[ModelInfo]:
        upstream_ids = await self._browser.model_ids()
        models = [ModelInfo(id="zai-web", owned_by="z-ai-web", provider=self.provider_id)]
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

    async def chat_completion(
        self,
        request: ChatCompletionRequest,
        session: Optional[SessionContext] = None,
    ) -> ChatCompletionResponse:
        if not self.supports_model(request.model):
            raise ProviderError("Unsupported Z.ai model", "invalid_model", self.provider_id)
        if request.tools:
            raise ProviderError("Z.ai tools are not enabled until E2 validation passes", "unsupported_tools", self.provider_id)
        if (request.provider_options or {}).get("search"):
            raise ProviderError("Z.ai search is not enabled until E2 validation passes", "unsupported_search", self.provider_id)

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

        return ChatCompletionResponse(
            id=self._generate_id(),
            created=self._current_timestamp(),
            model=request.model,
            choices=[Choice(index=0, message=Message(role="assistant", content="".join(pieces)), finish_reason="stop")],
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
            },
        )

    async def chat_completion_stream(
        self,
        request: ChatCompletionRequest,
        session: Optional[SessionContext] = None,
    ) -> AsyncIterator[ChatCompletionChunk]:
        if not self.supports_model(request.model):
            raise ProviderError("Unsupported Z.ai model", "invalid_model", self.provider_id)
        if request.tools:
            raise ProviderError("Z.ai tools are not enabled until E2 validation passes", "unsupported_tools", self.provider_id)
        if (request.provider_options or {}).get("search"):
            raise ProviderError("Z.ai search is not enabled until E2 validation passes", "unsupported_search", self.provider_id)

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
            tools=False,
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
