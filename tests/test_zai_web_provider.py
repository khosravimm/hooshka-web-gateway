import pytest

from adapters.zai_web_provider import create_zai_web_provider
from core.providers import ChatCompletionRequest, ProviderError


class FakeZaiTransport:
    frontend_version = "prod-fe-test"
    last_session_mode = "test"
    last_selected_model_label = None
    last_backend_request_model = None

    def __init__(self, *, authenticated=True, text=None):
        self.closed = False
        self.authenticated = authenticated
        self.text = text
        self.prompts = []
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
        self.prompts.append(prompt)
        self.last_selected_model_label = "GLM-5.3" if upstream_model == "glm-5.3" else None
        self.last_backend_request_model = upstream_model
        model = upstream_model
        text = self.text if self.text is not None else "ZAI_OK"
        yield {"type": "text_delta", "text": text, "chat_id": "chat-1", "model": model}

    async def close(self):
        self.closed = True


@pytest.mark.asyncio
async def test_zai_model_discovery_exposes_canonical_model():
    provider = create_zai_web_provider(provider_id="zai-web")
    provider._browser = FakeZaiTransport()

    models = await provider.list_models()

    assert [m.id for m in models] == ["zai-web", "zai:x-preview-l", "zai:glm-5.3", "zai:glm-4.7"]


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
async def test_zai_required_tool_envelope_becomes_openai_tool_call():
    provider = create_zai_web_provider(provider_id="zai-web")
    provider._browser = FakeZaiTransport(text='{"tool_calls":[{"name":"read_file","arguments":{"path":"README.md"}}]}')
    req = ChatCompletionRequest(
        model="zai-web",
        messages=[{"role": "user", "content": "read README"}],
        tools=[{"type": "function", "function": {"name": "read_file", "parameters": {"type":"object","properties":{"path":{"type":"string"}},"required":["path"]}}}],
        tool_choice={"type":"function","function":{"name":"read_file"}},
    )

    response = await provider.chat_completion(req)

    choice = response.choices[0]
    assert choice.finish_reason == "tool_calls"
    assert choice.message.content is None
    assert choice.message.tool_calls[0]["function"]["name"] == "read_file"
    assert '"path": "README.md"' in choice.message.tool_calls[0]["function"]["arguments"]
    assert "SYSTEM TOOL INSTRUCTIONS" in provider._browser.prompts[0]


@pytest.mark.asyncio
async def test_zai_required_tool_protocol_violation_fails_closed():
    provider = create_zai_web_provider(provider_id="zai-web")
    provider._browser = FakeZaiTransport(text="I cannot read files directly.")
    req = ChatCompletionRequest(
        model="zai-web",
        messages=[{"role": "user", "content": "read README"}],
        tools=[{"type": "function", "function": {"name": "read_file"}}],
        tool_choice="required",
    )

    with pytest.raises(ProviderError) as exc:
        await provider.chat_completion(req)

    assert exc.value.code == "tool_protocol_violation"


@pytest.mark.asyncio
async def test_zai_tool_result_continuation_serializes_tool_message():
    provider = create_zai_web_provider(provider_id="zai-web")
    provider._browser = FakeZaiTransport(text='{"final":"DONE"}')
    req = ChatCompletionRequest(
        model="zai-web",
        messages=[
            {"role": "assistant", "content": None, "tool_calls": [{"id": "call_1", "function": {"name": "read_file", "arguments": "{\"path\":\"README.md\"}"}}]},
            {"role": "tool", "tool_call_id": "call_1", "name": "read_file", "content": "# Project"},
            {"role": "user", "content": "continue"},
        ],
        tools=[{"type": "function", "function": {"name": "read_file"}}],
        tool_choice="auto",
    )

    response = await provider.chat_completion(req)

    assert response.choices[0].message.content == "DONE"
    assert response.choices[0].finish_reason == "stop"
    assert "[TOOL RESULT id=call_1 name=read_file]" in provider._browser.prompts[0]


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
async def test_zai_model_list_does_not_enumerate_guest_upstream_models():
    provider = create_zai_web_provider(provider_id="zai-web", require_authenticated=True)
    provider._browser = FakeZaiTransport(authenticated=False)

    models = await provider.list_models()

    assert [m.id for m in models] == ["zai-web"]


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


@pytest.mark.asyncio
async def test_zai_tool_result_raw_final_is_allowed():
    provider = create_zai_web_provider(provider_id="zai-web")
    provider._browser = FakeZaiTransport(text="RAW_DONE")
    req = ChatCompletionRequest(
        model="zai-web",
        messages=[
            {"role": "assistant", "content": None, "tool_calls": [{"id": "call_1", "function": {"name": "grep", "arguments": "{\"pattern\":\"KiloGate-WM\"}"}}]},
            {"role": "tool", "tool_call_id": "call_1", "name": "grep", "content": "Found matches"},
            {"role": "user", "content": "Then reply exactly: RAW_DONE"},
        ],
        tools=[{"type": "function", "function": {"name": "grep"}}],
        tool_choice="auto",
    )

    response = await provider.chat_completion(req)

    assert response.choices[0].message.content == "RAW_DONE"
    assert response.choices[0].finish_reason == "stop"


def test_zai_auto_tool_prompt_forces_one_explicitly_named_tool():
    provider = create_zai_web_provider(provider_id="zai-web")
    req = ChatCompletionRequest(
        model="zai-web",
        messages=[{"role": "user", "content": "You must use the available edit tool to modify the file."}],
        tools=[
            {"type": "function", "function": {"name": "read", "parameters": {}}},
            {"type": "function", "function": {"name": "edit", "parameters": {}}},
            {"type": "function", "function": {"name": "bash", "parameters": {}}},
        ],
        tool_choice="auto",
    )

    prompt = provider._request_text(req)

    assert "You MUST call the function named 'edit'" in prompt


def test_zai_auto_tool_prompt_does_not_force_after_tool_result():
    provider = create_zai_web_provider(provider_id="zai-web")
    req = ChatCompletionRequest(
        model="zai-web",
        messages=[
            {"role": "assistant", "content": None, "tool_calls": [{"id": "call_1", "function": {"name": "edit", "arguments": "{}"}}]},
            {"role": "tool", "tool_call_id": "call_1", "name": "edit", "content": "done"},
            {"role": "user", "content": "After the edit tool result, reply exactly DONE"},
        ],
        tools=[
            {"type": "function", "function": {"name": "edit", "parameters": {}}},
            {"type": "function", "function": {"name": "bash", "parameters": {}}},
        ],
        tool_choice="auto",
    )

    prompt = provider._request_text(req)

    assert "You MUST call the function named 'edit'" not in prompt
