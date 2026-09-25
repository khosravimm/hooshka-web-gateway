from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_chat_init_binds_event_handlers_once_and_refreshes_on_reentry():
    text = (ROOT / "control_panel_ui" / "chat.js").read_text(encoding="utf-8-sig")
    assert "let initialized = false;" in text
    assert "if (initialized) {" in text
    assert "populateProviders();" in text
    assert "initialized = true;" in text
    init_body = text.split("function init()", 1)[1].split("window.HwgChat", 1)[0]
    assert init_body.index("if (initialized) {") < init_body.index("addEventListener('change'")
    assert init_body.count("$('#chat-send').addEventListener('click', sendMessage);") == 1
    assert init_body.count("$('#chat-stop').addEventListener('click', stopStream);") == 1
    assert init_body.count("$('#chat-new').addEventListener('click', newConversation);") == 1
