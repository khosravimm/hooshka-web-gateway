import pytest

from adapters.zai_web_provider import create_zai_web_provider
from core.providers import ChatCompletionRequest, ProviderError


class FakeZaiTransport:
    frontend_version = "prod-fe-test"
    last_session_mode = "test"
    last_selected_model_label = None
    last_backend_request_model = None

    def __init__(self, *, authenticated=True):
        self.closed = False
        self.authenticated = authenticated
        self.last_session_mode = "authenticated" if authenticated else "guest"
        self._catalog = [
            {"id": "x-preview-l", "name": "GLM-5.3-Flash"},
            {"id": "glm-5.3", "name": "GLM-5.3"},
            {"id": "glm-4.7", "name": "GLM-4.7"},
        ]

    async def session_status(self):
        return {
            "authenticated": self.authenticated,
            "http_status": 200 if self.authenticated else 401,
            "mode": self.last_session_mode,
        }

    async def health(self):
        return True

    async def model_ids(self):
        return [x["id"] for x in self._catalog]

    async def model_catalog(self):
        return list(self._catalog)

    async def stream_text(self, prompt, *, upstream_model=None):
        self.last_selected_model_label = "GLM-5.3" if upstream_model == "glm-5.3" else None
        self.last_backend_request_model = upstream_model
        model = upstream_model
        yield {"type": "text_delta", "text": "ZAI_", "chat_id": "chat-1", "model": model}
        yield {"type": "text_delta", "text": "OK", "chat_id": "chat-1", "model": model}

    async def close(self):
        self.closed = True


@pytest.mark.asyncio
async def test_zai_model_discovery_does_not_advertise_without_current_e2():
    provider = create_zai_web_provider(provider_id="zai-web")
    provider._browser = FakeZaiTransport()

    models = await provider.list_models()

    assert [m.id for m in models] == []


@pytest.mark.asyncio
async def test_zai_completion_uses_transport_stream():
    provider = create_zai_web_provider(provider_id="zai-web")
    provider._browser = FakeZaiTransport()
    req = ChatCompletionRequest(model="zai-web", messages=[{"role": "user", "content": "hello"}])

    response = await provider.chat_completion(req)

    assert response.choices[0].message.content == "ZAI_OK"
    assert response.provider_meta["transport_mode"] == "browser_backend_controller"
    assert response.provider_meta["conversation_id"] == "chat-1"
    assert response.provider_meta["requested_upstream_model"] == "glm-5.3"
    assert response.provider_meta["backend_request_model"] == "glm-5.3"


@pytest.mark.asyncio
async def test_zai_explicit_glm53_routes_exact_upstream_model():
    provider = create_zai_web_provider(provider_id="zai-web")
    provider._browser = FakeZaiTransport()
    req = ChatCompletionRequest(model="zai:glm-5.3", messages=[{"role": "user", "content": "hello"}])

    response = await provider.chat_completion(req)

    assert response.model == "zai:glm-5.3"
    assert response.provider_meta["upstream_model"] == "glm-5.3"
    assert response.provider_meta["selected_model_label"] == "GLM-5.3"
    assert response.provider_meta["backend_request_model"] == "glm-5.3"


@pytest.mark.asyncio
async def test_zai_default_web_model_uses_configured_strongest_model():
    provider = create_zai_web_provider(provider_id="zai-web", default_upstream_model="glm-5.3")
    provider._browser = FakeZaiTransport()
    req = ChatCompletionRequest(model="zai-web", messages=[{"role": "user", "content": "hello"}])

    response = await provider.chat_completion(req)

    assert response.model == "zai-web"
    assert response.provider_meta["requested_upstream_model"] == "glm-5.3"
    assert response.provider_meta["backend_request_model"] == "glm-5.3"


@pytest.mark.asyncio
async def test_zai_rejects_tools_until_e2_validation():
    provider = create_zai_web_provider(provider_id="zai-web")
    provider._browser = FakeZaiTransport()
    req = ChatCompletionRequest(
        model="zai-web",
        messages=[{"role": "user", "content": "hello"}],
        tools=[{"type": "function", "function": {"name": "x"}}],
    )

    with pytest.raises(ProviderError) as exc:
        await provider.chat_completion(req)

    assert exc.value.code == "unsupported_tools"


@pytest.mark.asyncio
async def test_zai_guest_session_is_rejected_for_completion():
    provider = create_zai_web_provider(provider_id="zai-web", require_authenticated=True)
    provider._browser = FakeZaiTransport(authenticated=False)
    req = ChatCompletionRequest(model="zai-web", messages=[{"role": "user", "content": "hello"}])

    with pytest.raises(ProviderError) as exc:
        await provider.chat_completion(req)

    assert exc.value.code == "auth_required"
    assert exc.value.details["session_mode"] == "guest_disabled"


@pytest.mark.asyncio
async def test_zai_guest_session_is_not_healthy_when_authentication_required():
    provider = create_zai_web_provider(provider_id="zai-web", require_authenticated=True)
    provider._browser = FakeZaiTransport(authenticated=False)

    assert await provider.health_check() is False


@pytest.mark.asyncio
async def test_zai_model_list_is_empty_without_current_e2_even_when_guest():
    provider = create_zai_web_provider(provider_id="zai-web", require_authenticated=True)
    provider._browser = FakeZaiTransport(authenticated=False)

    models = await provider.list_models()

    assert [m.id for m in models] == []


@pytest.mark.asyncio
async def test_zai_stream_emits_text_and_terminal_chunk():
    provider = create_zai_web_provider(provider_id="zai-web")
    provider._browser = FakeZaiTransport()
    req = ChatCompletionRequest(model="zai-web", messages=[{"role": "user", "content": "hello"}], stream=True)

    chunks = []
    async for chunk in provider.chat_completion_stream(req):
        chunks.append(chunk)

    text = "".join((c.choices[0].delta.content or "") for c in chunks)
    assert text == "ZAI_OK"
    assert chunks[-1].choices[0].finish_reason == "stop"
    assert chunks[-1].provider_meta["requested_upstream_model"] == "glm-5.3"
    assert chunks[-1].provider_meta["backend_request_model"] == "glm-5.3"
