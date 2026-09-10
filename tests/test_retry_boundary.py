import asyncio

from adapters.chatgpt_web_provider import create_chatgpt_web_provider
from core.providers import ChatCompletionRequest, ProviderError


def test_post_submission_failure_is_not_replayed():
    provider = create_chatgpt_web_provider()
    calls = {"count": 0}

    async def ensure_page():
        return None

    async def fail_after_submit(request, session=None):
        calls["count"] += 1
        raise ProviderError(
            "ambiguous post-submit failure",
            "test_failure",
            provider.provider_id,
            details={"submission_started": True},
        )

    provider._ensure_page = ensure_page
    provider._do_chat_completion = fail_after_submit
    request = ChatCompletionRequest(model="chatgpt-web", messages=[{"role": "user", "content": "hello"}])

    try:
        asyncio.run(provider.chat_completion(request))
    except ProviderError:
        pass
    else:
        raise AssertionError("expected ProviderError")

    assert calls["count"] == 1


def test_pre_submission_failure_may_retry_once():
    provider = create_chatgpt_web_provider()
    calls = {"count": 0}

    async def ensure_page():
        return None

    async def cleanup():
        return None

    async def fail_before_submit(request, session=None):
        calls["count"] += 1
        raise ProviderError(
            "pre-submit failure",
            "test_failure",
            provider.provider_id,
            details={"submission_started": False},
        )

    provider._ensure_page = ensure_page
    provider._cleanup_connection = cleanup
    provider._do_chat_completion = fail_before_submit
    request = ChatCompletionRequest(model="chatgpt-web", messages=[{"role": "user", "content": "hello"}])

    try:
        asyncio.run(provider.chat_completion(request))
    except ProviderError:
        pass
    else:
        raise AssertionError("expected ProviderError")

    assert calls["count"] == 2
