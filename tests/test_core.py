import pytest
import asyncio
from core.providers import (
    Provider,
    ProviderConfig,
    ProviderType,
    ProviderCapabilities,
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
    ProviderError,
    ProviderUnavailableError,
    ProviderTimeoutError,
)
from core.mcp import MCPTranslator, MCPNormalizer, MCPSessionManager
from core.provider_registry import ProviderRegistry, ProviderRouter
from core.governance import RateLimiter, AuthManager, AuditLogger


class MockProvider(Provider):
    def __init__(self, provider_id="test-provider", should_fail=False, priority=10):
        config = ProviderConfig(
            provider_id=provider_id,
            provider_type=ProviderType.CUSTOM,
            enabled=True,
            priority=priority,
            capabilities=ProviderCapabilities(
                chat_completion=True,
                streaming=True,
                tools=False,
                max_context_tokens=4096,
                supported_models=["test-model"],
            ),
        )
        super().__init__(config)
        self._should_fail = should_fail
        self.call_count = 0
    
    async def health_check(self) -> bool:
        return not self._should_fail
    
    async def chat_completion(self, request, session=None):
        self.call_count += 1
        if self._should_fail:
            raise ProviderError("Simulated failure", "test_error", self.provider_id)
        
        return ChatCompletionResponse(
            id=self._generate_id(),
            created=self._current_timestamp(),
            model=request.model,
            choices=[
                Choice(
                    index=0,
                    message=Message(role="assistant", content="Test response"),
                    finish_reason="stop",
                )
            ],
            usage=Usage(prompt_tokens=10, completion_tokens=5, total_tokens=15),
            provider_meta={"call_count": self.call_count},
        )
    
    async def chat_completion_stream(self, request, session=None):
        self.call_count += 1
        if self._should_fail:
            raise ProviderError("Simulated stream failure", "test_error", self.provider_id)
        
        response_text = "Test streaming response"
        for i, char in enumerate(response_text):
            yield ChatCompletionChunk(
                id=self._generate_id(),
                created=self._current_timestamp(),
                model=request.model,
                choices=[
                    ChunkChoice(
                        index=0,
                        delta=Delta(role="assistant" if i == 0 else None, content=char),
                        finish_reason=None,
                    )
                ],
            )
        yield ChatCompletionChunk(
            id=self._generate_id(),
            created=self._current_timestamp(),
            model=request.model,
            choices=[
                ChunkChoice(
                    index=0,
                    delta=Delta(),
                    finish_reason="stop",
                )
            ],
        )
    
    async def list_models(self):
        return [
            ModelInfo(id="test-model", owned_by="test", provider=self.provider_id),
        ]
    
    async def close(self):
        pass


class TestProviderInterface:
    def test_provider_config(self):
        config = ProviderConfig(
            provider_id="test",
            provider_type=ProviderType.OPENAI_API,
            priority=50,
        )
        assert config.provider_id == "test"
        assert config.provider_type == ProviderType.OPENAI_API
        assert config.priority == 50
        assert config.enabled is True
    
    def test_provider_capabilities(self):
        caps = ProviderCapabilities(
            chat_completion=True,
            streaming=False,
            tools=True,
            max_context_tokens=8192,
        )
        assert caps.chat_completion is True
        assert caps.streaming is False
        assert caps.tools is True
        assert caps.max_context_tokens == 8192
    
    def test_chat_completion_request(self):
        req = ChatCompletionRequest(
            model="gpt-4",
            messages=[{"role": "user", "content": "Hello"}],
            temperature=0.7,
            stream=True,
        )
        assert req.model == "gpt-4"
        assert req.temperature == 0.7
        assert req.stream is True
        assert req.conversation_id is None
    
    def test_session_context(self):
        session = SessionContext(conversation_id="conv-123")
        assert session.conversation_id == "conv-123"
        assert session.provider_session_id is None
        assert isinstance(session.metadata, dict)


class TestMCPTranslator:
    def setup_method(self):
        self.provider = MockProvider()
        self.translator = MCPTranslator()
    
    def test_translate_basic_request(self):
        req = ChatCompletionRequest(
            model="gpt-4",
            messages=[{"role": "user", "content": "Hello"}],
        )
        translated = self.translator.translate_request(req, self.provider)
        
        assert translated.model == "gpt-4"
        assert translated.messages == req.messages
        assert translated.temperature == 1.0
    
    def test_translate_preserves_conversation_id(self):
        req = ChatCompletionRequest(
            model="gpt-4",
            messages=[{"role": "user", "content": "Hello"}],
            conversation_id="conv-123",
        )
        translated = self.translator.translate_request(req, self.provider)
        assert translated.conversation_id == "conv-123"


class TestMCPNormalizer:
    def setup_method(self):
        self.provider = MockProvider()
        self.normalizer = MCPNormalizer()
    
    def test_normalize_response_adds_provider_meta(self):
        response = ChatCompletionResponse(
            id="test-123",
            created=1234567890,
            model="gpt-4",
            choices=[
                Choice(
                    index=0,
                    message=Message(role="assistant", content="Hello"),
                    finish_reason="stop",
                )
            ],
            usage=Usage(prompt_tokens=5, completion_tokens=3, total_tokens=8),
        )
        normalized = self.normalizer.normalize_response(response, self.provider)
        
        assert normalized.provider_meta is not None
        assert normalized.provider_meta["provider_id"] == "test-provider"
        assert normalized.provider_meta["provider_type"] == "custom"
    
    def test_normalize_error_provider_error(self):
        error = ProviderError("Test error", "test_code", "test-provider", {"detail": "info"})
        normalized = self.normalizer.normalize_error(error, self.provider)
        
        assert normalized["error"]["message"] == "Test error"
        assert normalized["error"]["type"] == "test_code"
        assert normalized["error"]["provider"] == "test-provider"
        assert normalized["error"]["details"]["detail"] == "info"
    
    def test_normalize_error_generic(self):
        error = ValueError("Generic error")
        normalized = self.normalizer.normalize_error(error, self.provider)
        
        assert normalized["error"]["message"] == "Generic error"
        assert normalized["error"]["type"] == "internal_error"


class TestMCPSessionManager:
    def setup_method(self):
        self.manager = MCPSessionManager()
        self.provider = MockProvider()
    
    def test_get_or_create_session(self):
        session = self.manager.get_or_create_session("conv-1", self.provider)
        assert session["conversation_id"] == "conv-1"
        assert session["provider_id"] == "test-provider"
        assert session["message_count"] == 0
    
    def test_session_increments_count(self):
        self.manager.get_or_create_session("conv-1", self.provider)
        self.manager.get_or_create_session("conv-1", self.provider)
        session = self.manager.get_session("conv-1")
        assert session["message_count"] == 1
    
    def test_update_provider_session_id(self):
        self.manager.get_or_create_session("conv-1", self.provider)
        self.manager.update_provider_session_id("conv-1", "provider-sess-123")
        session = self.manager.get_session("conv-1")
        assert session["provider_session_id"] == "provider-sess-123"
    
    def test_delete_session(self):
        self.manager.get_or_create_session("conv-1", self.provider)
        self.manager.delete_session("conv-1")
        assert self.manager.get_session("conv-1") is None


class TestProviderRegistry:
    def setup_method(self):
        self.registry = ProviderRegistry()
        self.provider1 = MockProvider("provider-1", priority=100)
        self.provider2 = MockProvider("provider-2", priority=50)
    
    def test_register_and_get(self):
        self.registry.register(self.provider1)
        assert self.registry.get("provider-1") == self.provider1
        assert self.registry.get_default() == self.provider1
    
    def test_unregister(self):
        self.registry.register(self.provider1)
        assert self.registry.unregister("provider-1") is True
        assert self.registry.get("provider-1") is None
        assert self.registry.unregister("non-existent") is False
    
    def test_list_providers_sorted_by_priority(self):
        self.registry.register(self.provider1)
        self.registry.register(self.provider2)
        
        providers = self.registry.list_providers()
        assert providers[0].provider_id == "provider-2"
        assert providers[1].provider_id == "provider-1"
    
    def test_enabled_only_filter(self):
        self.provider2._config.enabled = False
        self.registry.register(self.provider1)
        self.registry.register(self.provider2)
        
        enabled = self.registry.list_providers(enabled_only=True)
        assert len(enabled) == 1
        assert enabled[0].provider_id == "provider-1"
        
        all_providers = self.registry.list_providers(enabled_only=False)
        assert len(all_providers) == 2


class TestProviderRouter:
    def setup_method(self):
        self.registry = ProviderRegistry()
        self.router = ProviderRouter(self.registry)
        self.provider = MockProvider()
        self.registry.register(self.provider)
    
    def test_select_by_provider_id(self):
        selected = self.router.select_provider(provider_id="test-provider")
        assert selected == self.provider
        
        selected = self.router.select_provider(provider_id="non-existent")
        assert selected is None
    
    def test_select_by_capability_streaming(self):
        self.provider._capabilities.streaming = True
        selected = self.router.select_provider(require_streaming=True)
        assert selected == self.provider
        
        self.provider._capabilities.streaming = False
        selected = self.router.select_provider(require_streaming=True)
        assert selected is None
    
    def test_select_by_model(self):
        self.provider._capabilities.supported_models = ["gpt-4", "gpt-3.5"]
        selected = self.router.select_provider(model="gpt-4")
        assert selected == self.provider
        
        selected = self.router.select_provider(model="claude-3")
        assert selected is None

    def test_empty_supported_models_is_not_wildcard(self):
        self.provider._capabilities.supported_models = []
        assert self.router.select_provider(model="anything") is None

    def test_model_resolution_does_not_cross_fallback(self):
        self.provider._capabilities.supported_models = ["chatgpt-web"]
        other = MockProvider(provider_id="other-provider", priority=1)
        other._capabilities.supported_models = ["qwen-web"]
        self.registry.register(other)

        assert self.router.select_provider(model="chatgpt-web") == self.provider
        assert self.router.select_provider(model="qwen-web") == other
        assert self.router.select_provider(model="unknown-web") is None


class TestRateLimiter:
    def setup_method(self):
        self.limiter = RateLimiter()
        self.limiter._default_rate = 10
        self.limiter._default_burst = 5
    
    def test_allows_within_limit(self):
        for _ in range(5):
            allowed, headers = self.limiter.check_rate_limit("user-1")
            assert allowed is True
            assert headers["remaining"] >= 0
    
    def test_blocks_over_limit(self):
        for _ in range(5):
            self.limiter.check_rate_limit("user-1")
        
        allowed, headers = self.limiter.check_rate_limit("user-1")
        assert allowed is False
        assert headers["remaining"] == 0
    
    def test_separate_identities(self):
        for _ in range(5):
            self.limiter.check_rate_limit("user-1")
        
        allowed, _ = self.limiter.check_rate_limit("user-2")
        assert allowed is True
    
    def test_provider_specific_limits(self):
        self.limiter.set_rate("chatgpt-web", 2, 2)
        
        allowed, _ = self.limiter.check_rate_limit("user-1", "chatgpt-web")
        assert allowed is True
        allowed, _ = self.limiter.check_rate_limit("user-1", "chatgpt-web")
        assert allowed is True
        allowed, _ = self.limiter.check_rate_limit("user-1", "chatgpt-web")
        assert allowed is False


class TestAuthManager:
    def setup_method(self):
        self.auth = AuthManager()
        self.auth._enabled = True
        self.auth.add_key("test-key-123", "user-1", {"role": "admin"})
    
    def test_verify_valid_key(self):
        result = self.auth.verify("test-key-123")
        assert result is not None
        assert result["identity"] == "user-1"
        assert result["metadata"]["role"] == "admin"
    
    def test_verify_invalid_key(self):
        result = self.auth.verify("invalid-key")
        assert result is None
    
    def test_disabled_auth_allows_anonymous(self):
        self.auth._enabled = False
        result = self.auth.verify("any-key")
        assert result is not None
        assert result["identity"] == "anonymous"

    def test_load_keys_accepts_legacy_string_identity(self):
        self.auth.load_keys({"legacy-key": "legacy-user"})
        result = self.auth.verify("legacy-key")
        assert result == {"identity": "legacy-user", "metadata": {}}


@pytest.mark.asyncio
class TestMockProviderIntegration:
    async def test_chat_completion_success(self):
        provider = MockProvider()
        request = ChatCompletionRequest(
            model="test-model",
            messages=[{"role": "user", "content": "Hello"}],
        )
        
        response = await provider.chat_completion(request)
        
        assert response.id.startswith("chatcmpl-")
        assert response.model == "test-model"
        assert response.choices[0].message.content == "Test response"
        assert response.usage.total_tokens == 15
    
    async def test_chat_completion_streaming(self):
        provider = MockProvider()
        request = ChatCompletionRequest(
            model="test-model",
            messages=[{"role": "user", "content": "Hello"}],
            stream=True,
        )
        
        chunks = []
        async for chunk in provider.chat_completion_stream(request):
            chunks.append(chunk)
        
        assert len(chunks) > 1
        assert chunks[-1].choices[0].finish_reason == "stop"
        full_content = "".join(c.choices[0].delta.content or "" for c in chunks[:-1])
        assert full_content == "Test streaming response"
    
    async def test_health_check(self):
        provider = MockProvider()
        assert await provider.health_check() is True
        
        failing = MockProvider(should_fail=True)
        assert await failing.health_check() is False
    
    async def test_list_models(self):
        provider = MockProvider()
        models = await provider.list_models()
        assert len(models) == 1
        assert models[0].id == "test-model"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])