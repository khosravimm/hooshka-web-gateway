from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_embedded_chat_is_fail_closed_before_provider_readiness_loads():
    html=(ROOT/'control_panel_ui'/'index.html').read_text(encoding='utf-8-sig')
    js=(ROOT/'control_panel_ui'/'chat.js').read_text(encoding='utf-8-sig')
    assert 'id="chat-provider" class="ctrl" disabled' in html
    assert 'id="chat-model" class="ctrl" disabled' in html
    assert 'id="chat-send" class="btn primary" type="button" disabled' in html
    assert "if (send) send.disabled = true;" in js
    assert "selectedProviderIsCurrentReady" in js
    assert "if (!selectedProviderIsCurrentReady())" in js
    assert "r.ready === true && r.current === true && r.state === 'READY'" in js
