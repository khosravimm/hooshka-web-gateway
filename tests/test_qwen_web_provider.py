import asyncio
import contextlib

import pytest

from adapters.qwen_web_provider import create_qwen_web_provider
from core.providers import ChatCompletionRequest, ProviderError


def asyncio_run(coro):
    return asyncio.run(coro)


async def _collect(async_iterable):
    return [item async for item in async_iterable]


async def _fake_model_ids():
    return ["qwen3.8-max", "qwen3.7-plus"]


async def _fake_authenticated_session():
    return {"authenticated": True, "session_mode": "authenticated", "status": 200}


async def _fake_guest_session():
    return {"authenticated": False, "session_mode": "guest", "status": 200}


def test_qwen_browser_provider_preserves_false_thinking_option(monkeypatch):
    provider = create_qwen_web_provider(
        provider_id="qwen-web",
        transport_mode="browser_controller",
        profile_dir=".runtime/test-qwen-profile",
        default_upstream_model="qwen3.7-plus",
    )
    captured = {}

    async def fake_stream_text(prompt, *, thinking=True, search=False, upstream_model=None):
        captured["prompt"] = prompt
        captured["thinking"] = thinking
        captured["search"] = search
        captured["upstream_model"] = upstream_model
        provider._browser.last_selected_models = [upstream_model]
        provider._browser.last_backend_request_model = upstream_model
        yield {"type": "text_delta", "text": "ok", "chat_id": "chat-1", "model": upstream_model}
        yield {"type": "done", "text": "", "chat_id": "chat-1", "model": upstream_model}

    monkeypatch.setattr(provider._browser, "stream_text", fake_stream_text)
    monkeypatch.setattr(provider._browser, "model_ids", _fake_model_ids)
    monkeypatch.setattr(provider._browser, "session_status", _fake_authenticated_session)

    request = ChatCompletionRequest(
        model="qwen-web",
        messages=[{"role": "user", "content": "hello"}],
        provider_options={"thinking": False, "search": True},
    )

    response = asyncio_run(provider.chat_completion(request))

    assert response.model == "qwen-web"
    assert response.choices[0].message.content == "ok"
    assert captured == {"prompt": "hello", "thinking": False, "search": True, "upstream_model": "qwen3.7-plus"}
    asyncio_run(provider.close())


def test_qwen_browser_stream_preserves_false_thinking_option(monkeypatch):
    provider = create_qwen_web_provider(
        provider_id="qwen-web",
        transport_mode="browser_controller",
        profile_dir=".runtime/test-qwen-profile",
        default_upstream_model="qwen3.7-plus",
    )
    captured = {}

    async def fake_stream_text(prompt, *, thinking=True, search=False, upstream_model=None):
        captured["prompt"] = prompt
        captured["thinking"] = thinking
        captured["search"] = search
        captured["upstream_model"] = upstream_model
        provider._browser.last_selected_models = [upstream_model]
        provider._browser.last_backend_request_model = upstream_model
        yield {"type": "text_delta", "text": "o", "chat_id": "chat-1", "model": upstream_model}
        yield {"type": "text_delta", "text": "k", "chat_id": "chat-1", "model": upstream_model}
        yield {"type": "done", "text": "", "chat_id": "chat-1", "model": upstream_model}

    monkeypatch.setattr(provider._browser, "stream_text", fake_stream_text)
    monkeypatch.setattr(provider._browser, "model_ids", _fake_model_ids)
    monkeypatch.setattr(provider._browser, "session_status", _fake_authenticated_session)

    request = ChatCompletionRequest(
        model="qwen-web",
        messages=[{"role": "user", "content": "hello"}],
        provider_options={"thinking": False, "search": True},
    )

    chunks = list(asyncio_run(_collect(provider.chat_completion_stream(request))))
    text = "".join(c.choices[0].delta.content or "" for c in chunks)
    assert text == "ok"
    assert chunks[-1].choices[0].finish_reason == "stop"
    assert captured == {"prompt": "hello", "thinking": False, "search": True, "upstream_model": "qwen3.7-plus"}
    asyncio_run(provider.close())


def test_qwen_explicit_max_routes_exact_upstream_model(monkeypatch):
    provider = create_qwen_web_provider(
        provider_id="qwen-web",
        transport_mode="browser_controller",
        profile_dir=".runtime/test-qwen-profile",
    )
    captured = {}

    async def fake_stream_text(prompt, *, thinking=True, search=False, upstream_model=None):
        captured["upstream_model"] = upstream_model
        provider._browser.last_selected_models = [upstream_model]
        provider._browser.last_backend_request_model = upstream_model
        yield {"type": "text_delta", "text": "ok", "chat_id": "chat-max", "model": upstream_model}
        yield {"type": "done", "text": "", "chat_id": "chat-max", "model": upstream_model}

    monkeypatch.setattr(provider._browser, "stream_text", fake_stream_text)
    monkeypatch.setattr(provider._browser, "model_ids", _fake_model_ids)
    monkeypatch.setattr(provider._browser, "session_status", _fake_authenticated_session)
    request = ChatCompletionRequest(
        model="qwen:qwen3.8-max",
        messages=[{"role": "user", "content": "hello"}],
    )

    response = asyncio_run(provider.chat_completion(request))

    assert response.choices[0].message.content == "ok"
    assert captured["upstream_model"] == "qwen3.8-max"
    assert response.provider_meta["upstream_model"] == "qwen3.8-max"
    asyncio_run(provider.close())


def test_qwen_default_web_model_uses_configured_strongest_model(monkeypatch):
    provider = create_qwen_web_provider(
        provider_id="qwen-web",
        transport_mode="browser_controller",
        profile_dir=".runtime/test-qwen-profile",
        default_upstream_model="qwen3.8-max",
    )
    captured = {}

    async def fake_stream_text(prompt, *, thinking=True, search=False, upstream_model=None):
        captured["upstream_model"] = upstream_model
        provider._browser.last_selected_models = [upstream_model]
        provider._browser.last_backend_request_model = upstream_model
        yield {"type": "text_delta", "text": "ok", "chat_id": "chat-max", "model": upstream_model}
        yield {"type": "done", "text": "", "chat_id": "chat-max", "model": upstream_model}

    monkeypatch.setattr(provider._browser, "stream_text", fake_stream_text)
    monkeypatch.setattr(provider._browser, "model_ids", _fake_model_ids)
    monkeypatch.setattr(provider._browser, "session_status", _fake_authenticated_session)
    request = ChatCompletionRequest(
        model="qwen-web",
        messages=[{"role": "user", "content": "hello"}],
    )

    response = asyncio_run(provider.chat_completion(request))

    assert response.model == "qwen-web"
    assert captured["upstream_model"] == "qwen3.8-max"
    assert response.provider_meta["upstream_model"] == "qwen3.8-max"
    asyncio_run(provider.close())


def test_qwen_rejects_guest_session_by_policy(monkeypatch):
    provider = create_qwen_web_provider(
        provider_id="qwen-web",
        transport_mode="browser_controller",
        profile_dir=".runtime/test-qwen-profile",
        require_authenticated=True,
    )
    monkeypatch.setattr(provider._browser, "session_status", _fake_guest_session)
    monkeypatch.setattr(provider._browser, "model_ids", _fake_model_ids)

    request = ChatCompletionRequest(
        model="qwen-web",
        messages=[{"role": "user", "content": "hello"}],
    )

    with pytest.raises(ProviderError) as exc:
        asyncio_run(provider.chat_completion(request))
    assert exc.value.code == "auth_required"
    assert "guest mode is disabled" in str(exc.value)
    asyncio_run(provider.close())


def test_qwen_rejects_tools_until_e2_validated():
    provider = create_qwen_web_provider(
        provider_id="qwen-web",
        transport_mode="browser_controller",
    )
    request = ChatCompletionRequest(
        model="qwen-web",
        messages=[{"role": "user", "content": "call tool"}],
        tools=[
            {
                "type": "function",
                "function": {"name": "probe", "parameters": {"type": "object"}},
            },
        ],
    )

    with pytest.raises(ProviderError) as exc:
        asyncio_run(provider.chat_completion(request))
    assert exc.value.code == "unsupported_tools"
    with contextlib.suppress(Exception):
        asyncio_run(provider.close())
