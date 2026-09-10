import pytest

from adapters.zai_web_provider import create_zai_web_provider
from core.providers import ChatCompletionRequest, ProviderError


class FakeResponse:
    def __init__(self, status_code=200, data=None, content_type="application/json"):
        self.status_code = status_code
        self._data = data or {"data": []}
        self.headers = {"content-type": content_type}
        self.ok = 200 <= status_code < 300

    def json(self):
        return self._data


@pytest.mark.asyncio
async def test_zai_model_discovery_maps_upstream_models(monkeypatch):
    provider = create_zai_web_provider(provider_id="zai-web")

    def fake_get(url, headers, timeout):
        assert url == "https://chat.z.ai/api/models"
        assert headers["X-FE-Version"] == "prod-fe-1.1.93"
        return FakeResponse(data={"data": [{"id": "x-preview-l"}, {"id": "glm-4.7"}]})

    monkeypatch.setattr("adapters.zai_web_provider.requests.get", fake_get)

    models = await provider.list_models()
    assert [m.id for m in models] == ["zai-web", "zai:x-preview-l", "zai:glm-4.7"]


@pytest.mark.asyncio
async def test_zai_completion_is_fail_closed():
    provider = create_zai_web_provider(provider_id="zai-web", transport_mode="backend_discovery_only")
    req = ChatCompletionRequest(model="zai-web", messages=[{"role": "user", "content": "hello"}])

    with pytest.raises(ProviderError) as exc:
        await provider.chat_completion(req)

    assert exc.value.code == "challenge_required"
    assert exc.value.details["completion_path"] == "/api/v2/chat/completions"


@pytest.mark.asyncio
async def test_zai_stream_is_fail_closed():
    provider = create_zai_web_provider(provider_id="zai-web", transport_mode="backend_discovery_only")
    req = ChatCompletionRequest(model="zai-web", messages=[{"role": "user", "content": "hello"}], stream=True)

    with pytest.raises(ProviderError) as exc:
        async for _ in provider.chat_completion_stream(req):
            pass

    assert exc.value.code == "challenge_required"
