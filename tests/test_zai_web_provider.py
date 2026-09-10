import pytest

from adapters.zai_web_provider import create_zai_web_provider
from core.providers import ChatCompletionRequest, ProviderError


class FakeZaiTransport:
    frontend_version = "prod-fe-test"
    last_session_mode = "test"

    def __init__(self):
        self.closed = False

    async def health(self):
        return True

    async def model_ids(self):
        return ["x-preview-l", "glm-4.7"]

    async def stream_text(self, prompt):
        yield {"type": "text_delta", "text": "ZAI_", "chat_id": "chat-1", "model": "glm-4.7"}
        yield {"type": "text_delta", "text": "OK", "chat_id": "chat-1", "model": "glm-4.7"}

    async def close(self):
        self.closed = True


@pytest.mark.asyncio
async def test_zai_model_discovery_exposes_canonical_model():
    provider = create_zai_web_provider(provider_id="zai-web")
    provider._browser = FakeZaiTransport()

    models = await provider.list_models()

    assert [m.id for m in models] == ["zai-web"]


@pytest.mark.asyncio
async def test_zai_completion_uses_transport_stream():
    provider = create_zai_web_provider(provider_id="zai-web")
    provider._browser = FakeZaiTransport()
    req = ChatCompletionRequest(model="zai-web", messages=[{"role": "user", "content": "hello"}])

    response = await provider.chat_completion(req)

    assert response.choices[0].message.content == "ZAI_OK"
    assert response.provider_meta["transport_mode"] == "browser_backend_controller"
    assert response.provider_meta["conversation_id"] == "chat-1"


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
