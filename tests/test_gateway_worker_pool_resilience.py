from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAIN = ROOT / "main.py"


def source() -> str:
    return MAIN.read_text(encoding="utf-8-sig")


def body_between(text: str, start_marker: str, end_marker: str) -> str:
    start = text.index(start_marker)
    end = text.index(end_marker, start)
    return text[start:end]


def test_provider_work_is_bounded_by_semaphore():
    text = source()
    assert "threading.BoundedSemaphore" in text
    assert "HOOSHKA_GW_PROVIDER_CONCURRENCY" in text
    assert "def _try_acquire_provider_slot" in text
    assert "def _release_provider_slot" in text
    assert "provider_busy" in text


def test_health_is_fast_and_does_not_touch_browser_or_provider_calls():
    text = source()
    health_body = body_between(text, '@app.route("/health", methods=["GET"])', '@app.route("/ready", methods=["GET"])')
    assert '"provider_runtime": _provider_state()' in health_body
    assert "provider.health_check" not in health_body
    assert "provider.list_models" not in health_body
    assert "_run_async" not in health_body


def test_ready_is_fast_static_and_deep_health_is_separate():
    text = source()
    ready_body = body_between(text, '@app.route("/ready", methods=["GET"])', '@app.route("/health/deep", methods=["GET"])')
    assert '"mode": "fast"' in ready_body
    assert "provider.health_check" not in ready_body
    assert "provider.list_models" not in ready_body
    assert "_run_async" not in ready_body

    deep_body = body_between(text, '@app.route("/health/deep", methods=["GET"])', '@app.route("/modes", methods=["GET"])')
    assert "provider.health_check" in deep_body
    assert "asyncio.wait_for" in deep_body
    assert '_try_acquire_provider_slot("deep_health"' in deep_body
    assert "timeout=2.0" in deep_body
    assert "timeout=3.0" in deep_body


def test_models_endpoint_is_fast_static_and_does_not_enumerate_live_browsers():
    text = source()
    models_body = body_between(text, '@app.route("/v1/models", methods=["GET"])', '@app.route("/v1/chat/completions", methods=["POST"])')
    assert '"mode": "fast_static"' in models_body
    assert "_static_models_for_provider(provider)" in models_body
    assert "provider.list_models" not in models_body
    assert "_run_async" not in models_body


def test_chat_endpoints_acquire_and_release_provider_slots():
    text = source()
    chat_body = body_between(text, '@app.route("/v1/chat/completions", methods=["POST"])', '    def _stream_response')
    assert '_try_acquire_provider_slot("chat_completions"' in chat_body
    assert '_provider_busy_response("chat_completions"' in chat_body
    assert '_release_provider_slot("chat_completions"' in chat_body

    code_body = body_between(text, '@app.route("/v1/chat/code", methods=["POST"])', '@app.route("/v1/chat/conversation", methods=["POST"])')
    assert '_try_acquire_provider_slot("code_chat"' in code_body
    assert '_release_provider_slot("code_chat"' in code_body

    conversation_body = body_between(text, '@app.route("/v1/chat/conversation", methods=["POST"])', '    return app')
    assert '_try_acquire_provider_slot("conversation_chat"' in conversation_body
    assert '_release_provider_slot("conversation_chat"' in conversation_body


def test_async_timeout_is_recorded_for_operations_diagnostics():
    text = source()
    run_async_body = body_between(text, "    def _run_async", "    def _shutdown_async_loop")
    assert "FutureTimeoutError" in run_async_body
    assert "_provider_timeouts += 1" in run_async_body
    assert "Provider async operation timed out" in run_async_body
