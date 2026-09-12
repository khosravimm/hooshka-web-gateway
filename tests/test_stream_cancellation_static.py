from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_stream_disconnect_calls_provider_cancel_hook_before_future_cancel():
    text = read("main.py")
    start = text.index("def _stream_response")
    end = text.index('@app.route("/v1/chat/code"', start)
    block = text[start:end]
    assert 'provider.cancel_active_generation("stream_client_disconnected")' in block
    assert "future.cancel()" in block
    assert block.index('provider.cancel_active_generation("stream_client_disconnected")') < block.index("future.cancel()")


def test_provider_contract_exposes_default_cancel_hook():
    text = read("core/providers.py")
    assert "async def cancel_active_generation" in text
    assert '"supported": False' in text


def test_qwen_cancel_uses_frontend_stop_response():
    text = read("adapters/qwen_browser_transport.py")
    assert "async def cancel_active_generation" in text
    assert "stopResponse" in text
    assert "stopAllResponses" in text


def test_zai_and_deepseek_cancel_click_provider_stop_control():
    for rel in ["adapters/zai_browser_transport.py", "adapters/deepseek_browser_transport.py"]:
        text = read(rel)
        assert "async def cancel_active_generation" in text
        assert "dom_stop_button" in text
        assert "Stopping" in text and "failed/cancelled stream" in text


def test_web_providers_delegate_or_implement_cancel():
    for rel in [
        "adapters/qwen_web_provider.py",
        "adapters/zai_web_provider.py",
        "adapters/deepseek_web_provider.py",
        "adapters/chatgpt_web_provider.py",
    ]:
        assert "async def cancel_active_generation" in read(rel)


def test_stream_uses_keepalive_to_surface_disconnects():
    text = read("main.py")
    start = text.index("def _stream_response")
    end = text.index('@app.route("/v1/chat/code"', start)
    block = text[start:end]
    assert "event_queue.get(timeout=2)" in block
    assert ": keepalive" in block
    assert "queue.Empty" in block


def test_dom_cancel_records_escape_as_attempt_not_proof():
    for rel in ["adapters/zai_browser_transport.py", "adapters/deepseek_browser_transport.py"]:
        text = read(rel)
        assert "escape_sent" in text
        assert "attempted" in text
        assert "do not treat it as proof" in text


def test_deepseek_cancel_uses_viewport_and_explicit_controls_only():
    text = read("adapters/deepseek_browser_transport.py")
    assert "visibleInViewport" in text
    assert "target_not_clickable" in text
    assert "typeof target.click !== 'function'" in text
    assert "const squareIcon = false" in text
    assert "button,[role=\"button\"]" in text


def test_chatgpt_cancel_uses_explicit_stop_and_post_click_confirmation():
    text = read("adapters/chatgpt_web_provider.py")
    block = text[text.index("async def cancel_active_generation"):text.index("async def close", text.index("async def cancel_active_generation"))]
    assert "visibleInViewport" in block
    assert "data-testid') === 'stop-button'" in block
    assert "stop generating" in block
    assert "stop streaming" in block
    assert "remaining_stop_controls" in block
    assert "Escape is recorded as an attempt, never as proof" in block
    assert "result[\"cancelled\"] = bool((probe or {}).get(\"clicked\")) and" in block
