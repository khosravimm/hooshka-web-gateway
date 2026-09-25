import time
from pathlib import Path

import main
from core.mcp import mcp_session_manager
from core.providers import ChatCompletionResponse, Choice, Message, Usage

ROOT = Path(__file__).resolve().parent.parent


def test_conversation_endpoint_creates_and_reuses_session(monkeypatch):
    app = main.create_app(str(ROOT / "config.yaml"))
    app.config["TESTING"] = True
    client = app.test_client()
    provider = main.provider_registry.get("deepseek-web")
    conversation_id = "audit-session-lifecycle"
    mcp_session_manager.delete_session(conversation_id)
    seen_sessions = []

    async def fake_chat_completion(req, session):
        seen_sessions.append(None if session is None else session.conversation_id)
        return ChatCompletionResponse(
            id="chatcmpl-test", created=int(time.time()), model="deepseek-web",
            choices=[Choice(index=0, message=Message(role="assistant", content="OK"), finish_reason="stop")],
            usage=Usage(prompt_tokens=1, completion_tokens=1, total_tokens=2),
            provider_meta={},
        )

    monkeypatch.setattr(provider, "chat_completion", fake_chat_completion)
    payload = {
        "model": "deepseek-web",
        "provider": "deepseek-web",
        "conversation_id": conversation_id,
        "messages": [{"role": "user", "content": "hello"}],
        "stream": False,
    }
    first = client.post("/v1/chat/conversation", json=payload)
    assert first.status_code == 200
    assert first.get_json()["conversation_id"] == conversation_id
    session = mcp_session_manager.get_session(conversation_id)
    assert session is not None
    assert session["provider_id"] == "deepseek-web"
    assert session["message_count"] == 0
    assert seen_sessions == [conversation_id]

    second = client.post("/v1/chat/conversation", json=payload)
    assert second.status_code == 200
    session = mcp_session_manager.get_session(conversation_id)
    assert session["message_count"] == 1
    assert seen_sessions == [conversation_id, conversation_id]
    mcp_session_manager.delete_session(conversation_id)
