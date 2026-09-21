"""SDK contract tests (mocked HTTP, no live gateway)."""
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "sdk" / "python"))

import pytest

from hwg_client import HwgClient, HwgError


def _client_with_mock(payload=None, status=200):
    c = HwgClient(base_url="http://127.0.0.1:9")
    resp = MagicMock(status_code=status)
    resp.json.return_value = payload or {}
    c._session = MagicMock()
    c._session.get.return_value = resp
    c._session.post.return_value = resp
    return c


def test_models_lists_data():
    c = _client_with_mock({"object": "list", "data": [{"id": "chatgpt-web"}]})
    assert c.models() == [{"id": "chatgpt-web"}]


def test_chat_posts_non_streaming():
    c = _client_with_mock({"id": "x", "choices": []})
    body = c.chat("chatgpt-web", [{"role": "user", "content": "hi"}])
    assert body["id"] == "x"
    sent = c._session.post.call_args[0][0]
    assert sent.endswith("/v1/chat/completions")
    assert c._session.post.call_args[1]["json"]["stream"] is False


def test_respond_posts_to_responses():
    c = _client_with_mock({"object": "response", "output": []})
    body = c.respond("chatgpt-web", "hi")
    assert body["object"] == "response"
    assert c._session.post.call_args[0][0].endswith("/v1/responses")


def test_http_error_raises_structured():
    c = _client_with_mock({"error": {"code": "model_not_found"}}, status=404)
    with pytest.raises(HwgError) as ei:
        c.models()
    assert ei.value.status == 404


def test_chat_stream_yields_until_done():
    c = HwgClient(base_url="http://127.0.0.1:9")
    ctx = MagicMock(status_code=200)
    ctx.iter_lines.return_value = iter([
        'data: {"x": 1}', "", "data: [DONE]", "data: {\"late\": true}"])
    cm = MagicMock()
    cm.__enter__.return_value = ctx
    cm.__exit__.return_value = False
    c._session = MagicMock()
    c._session.post.return_value = cm
    assert list(c.chat_stream("m", [])) == [{"x": 1}]
