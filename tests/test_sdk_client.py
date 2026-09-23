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


def test_contract_discovery_methods():
    c=_client_with_mock({"openapi":"3.1.0"})
    assert c.openapi()["openapi"]=="3.1.0"
    assert c._session.get.call_args[0][0].endswith("/v1/contracts/openapi.json")

def test_structured_error_preserves_message_code_details_provider():
    c=_client_with_mock({"error":{"message":"unsupported","code":"unsupported_media_type","details":{"media":"image"},"provider":"deepseek-web"}},status=400)
    with pytest.raises(HwgError) as ei: c.chat("deepseek-web",[])
    e=ei.value
    assert str(e)=="unsupported" and e.code=="unsupported_media_type" and e.details=={"media":"image"} and e.provider=="deepseek-web"

def test_provider_selection_is_explicit_in_chat_body():
    c=_client_with_mock({"id":"x"})
    c.chat("deepseek-web",[{"role":"user","content":"hi"}],provider="deepseek-web")
    assert c._session.post.call_args[1]["json"]["provider"]=="deepseek-web"

def test_multimodal_helpers_use_canonical_part_types():
    assert HwgClient.text_part("x")=={"type":"text","text":"x"}
    assert HwgClient.image_part("data:image/png;base64,AA==")["type"]=="input_image"
    assert HwgClient.file_part("D:/x.pdf")["type"]=="input_file"


def test_cancel_posts_public_cancellation_contract():
    c=_client_with_mock({"object":"chat.cancel.result","provider":"deepseek-web","cancelled":True})
    body=c.cancel(conversation_id="conv-1",reason="user_stop")
    assert body["cancelled"] is True
    assert c._session.post.call_args[0][0].endswith("/v1/chat/cancel")
    sent=c._session.post.call_args[1]["json"]
    assert sent=={"reason":"user_stop","conversation_id":"conv-1"}

def test_python_sdk_serializes_profile_account_target():
    c=_client_with_mock({"id":"x"})
    c.chat("deepseek-web",[{"role":"user","content":"hi"}],provider="deepseek-web",profile_id="deepseek-web:default",account_id="deepseek-web:default-account")
    body=c._session.post.call_args[1]["json"]
    assert body["provider"]=="deepseek-web"
    assert body["profile_id"]=="deepseek-web:default"
    assert body["account_id"]=="deepseek-web:default-account"

def test_python_sdk_uploads_multipart_and_can_delete(tmp_path):
    c=_client_with_mock({"data":[{"id":"up1"}]})
    c._session.delete.return_value = c._session.post.return_value
    f=tmp_path / "marker.txt"
    f.write_text("MARKER",encoding="utf-8")
    body=c.upload([f],provider="deepseek-web")
    assert body["data"][0]["id"]=="up1"
    kwargs=c._session.post.call_args[1]
    assert kwargs["data"]["provider"]=="deepseek-web"
    assert kwargs["files"][0][0]=="files"
    c.delete_upload("up1")
    assert c._session.delete.call_args[0][0].endswith("/v1/uploads/up1")

def test_python_sdk_respond_serializes_profile_account_target():
    c=_client_with_mock({"object":"response","output":[]})
    c.respond("deepseek-web","hi",provider="deepseek-web",profile_id="deepseek-web:default",account_id="deepseek-web:default-account")
    body=c._session.post.call_args[1]["json"]
    assert body["provider"]=="deepseek-web"
    assert body["profile_id"]=="deepseek-web:default"
    assert body["account_id"]=="deepseek-web:default-account"
