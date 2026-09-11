import pytest

from adapters.deepseek_web_provider import create_deepseek_web_provider
from core.providers import ChatCompletionRequest, ProviderError


TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read a project file",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"],
            },
        },
    }
]


class FakeDeepSeekTransport:
    def __init__(self, *, authenticated=True, text="DEEPSEEK_OK"):
        self.authenticated = authenticated
        self.text = text
        self.last_conversation_url = "https://chat.deepseek.com/a/chat/s/test"
        self.last_block_signals = {"captcha": False, "suspended_or_muted": False, "login": False}
        self.closed = False
        self.prompts = []

    async def session_status(self):
        return {
            "authenticated": self.authenticated,
            "mode": "authenticated" if self.authenticated else "blocked_or_guest",
            "signals": dict(self.last_block_signals),
        }

    async def health(self):
        return self.authenticated

    async def stream_text(self, prompt, *, new_chat=True):
        self.prompts.append(prompt)
        yield {"type": "text_delta", "text": self.text, "conversation_id": self.last_conversation_url}

    async def close(self):
        self.closed = True


@pytest.mark.asyncio
async def test_deepseek_model_list_exposes_canonical_model():
    provider = create_deepseek_web_provider()
    provider._browser = FakeDeepSeekTransport()

    models = await provider.list_models()

    assert [m.id for m in models] == ["deepseek-web"]
    assert models[0].provider == "deepseek-web"


@pytest.mark.asyncio
async def test_deepseek_completion_uses_webchat_transport():
    provider = create_deepseek_web_provider()
    provider._browser = FakeDeepSeekTransport(text="DEEPSEEK_OK")
    req = ChatCompletionRequest(model="deepseek-web", messages=[{"role": "user", "content": "hello"}])

    response = await provider.chat_completion(req)

    assert response.choices[0].message.content == "DEEPSEEK_OK"
    assert response.choices[0].finish_reason == "stop"
    assert response.provider_meta["transport_mode"] == "browser_ui"
    assert response.provider_meta["conversation_id"] == "https://chat.deepseek.com/a/chat/s/test"


@pytest.mark.asyncio
async def test_deepseek_required_tool_envelope_becomes_openai_tool_call():
    provider = create_deepseek_web_provider()
    provider._browser = FakeDeepSeekTransport(
        text='{"tool_calls":[{"name":"read_file","arguments":{"path":"README.md"}}]}'
    )
    req = ChatCompletionRequest(
        model="deepseek-web",
        messages=[{"role": "user", "content": "read README"}],
        tools=TOOLS,
        tool_choice={"type": "function", "function": {"name": "read_file"}},
    )

    response = await provider.chat_completion(req)

    choice = response.choices[0]
    assert choice.finish_reason == "tool_calls"
    assert choice.message.content is None
    assert choice.message.tool_calls[0]["function"]["name"] == "read_file"
    assert '"path": "README.md"' in choice.message.tool_calls[0]["function"]["arguments"]
    assert "SYSTEM TOOL INSTRUCTIONS" in provider._browser.prompts[0]


@pytest.mark.asyncio
async def test_deepseek_tool_result_continuation_serializes_tool_message():
    provider = create_deepseek_web_provider()
    provider._browser = FakeDeepSeekTransport(text='{"final":"DONE"}')
    req = ChatCompletionRequest(
        model="deepseek-web",
        messages=[
            {"role": "assistant", "content": None, "tool_calls": [{"id": "call_1", "function": {"name": "read_file", "arguments": "{\"path\":\"README.md\"}"}}]},
            {"role": "tool", "tool_call_id": "call_1", "name": "read_file", "content": "# Project"},
            {"role": "user", "content": "continue"},
        ],
        tools=TOOLS,
        tool_choice="auto",
    )

    response = await provider.chat_completion(req)

    assert response.choices[0].message.content == "DONE"
    assert response.choices[0].finish_reason == "stop"
    assert "[TOOL RESULT id=call_1 name=read_file]" in provider._browser.prompts[0]


@pytest.mark.asyncio
async def test_deepseek_required_tool_protocol_violation_fails_closed():
    provider = create_deepseek_web_provider()
    provider._browser = FakeDeepSeekTransport(text="I cannot read files directly.")
    req = ChatCompletionRequest(
        model="deepseek-web",
        messages=[{"role": "user", "content": "read README"}],
        tools=TOOLS,
        tool_choice="required",
    )

    with pytest.raises(ProviderError) as exc:
        await provider.chat_completion(req)

    assert exc.value.code == "tool_protocol_violation"


@pytest.mark.asyncio
async def test_deepseek_guest_session_is_rejected():
    provider = create_deepseek_web_provider(require_authenticated=True)
    provider._browser = FakeDeepSeekTransport(authenticated=False)
    req = ChatCompletionRequest(model="deepseek-web", messages=[{"role": "user", "content": "hello"}])

    with pytest.raises(ProviderError) as exc:
        await provider.chat_completion(req)

    assert exc.value.code == "auth_required"


@pytest.mark.asyncio
async def test_deepseek_stream_emits_terminal_chunk():
    provider = create_deepseek_web_provider()
    provider._browser = FakeDeepSeekTransport(text="STREAM_OK")
    req = ChatCompletionRequest(model="deepseek-web", messages=[{"role": "user", "content": "hello"}], stream=True)

    chunks = []
    async for chunk in provider.chat_completion_stream(req):
        chunks.append(chunk)

    assert "".join(c.choices[0].delta.content or "" for c in chunks) == "STREAM_OK"
    assert chunks[-1].choices[0].finish_reason == "stop"


@pytest.mark.asyncio
async def test_deepseek_tool_result_final_is_allowed_even_if_user_mentions_tools():
    provider = create_deepseek_web_provider()
    provider._browser = FakeDeepSeekTransport(text='{"final":"AFTER_TOOL_DONE"}')
    req = ChatCompletionRequest(
        model="deepseek-web",
        messages=[
            {"role": "assistant", "content": None, "tool_calls": [{"id": "call_1", "function": {"name": "read", "arguments": "{\"filePath\":\"README.md\"}"}}]},
            {"role": "tool", "tool_call_id": "call_1", "name": "read", "content": "# Project"},
            {"role": "user", "content": "Use tools to read README.md. Then reply exactly: AFTER_TOOL_DONE"},
        ],
        tools=TOOLS,
        tool_choice="auto",
    )

    response = await provider.chat_completion(req)

    assert response.choices[0].message.content == "AFTER_TOOL_DONE"
    assert response.choices[0].finish_reason == "stop"
