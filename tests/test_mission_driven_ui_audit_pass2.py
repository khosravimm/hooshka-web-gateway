from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / 'control_panel_ui' / 'index.html').read_text(encoding='utf-8-sig')
PANEL = (ROOT / 'control_panel_ui' / 'panel.js').read_text(encoding='utf-8-sig')
CHAT = (ROOT / 'control_panel_ui' / 'chat.js').read_text(encoding='utf-8-sig')
BACKEND = (ROOT / 'control_panel.py').read_text(encoding='utf-8-sig')


def test_runtime_uses_governed_open_action_not_raw_external_link():
    assert 'data-open="1"' in PANEL
    assert 'target="_blank" rel="noopener">${p.home_url' not in PANEL


def test_account_readiness_has_reason_next_action_and_probe():
    assert 'چرا/قدم بعد' in PANEL
    assert 'data-provider-ready' in PANEL
    assert 'Evidence منقضی شده' in PANEL


def test_models_show_certification_scope_from_readiness_records():
    assert 'models-certification-scope' in HTML
    assert "api('/readiness')" in PANEL
    assert "r.account_id" in PANEL and "r.model" in PANEL


def test_chat_send_is_gated_by_current_readiness_evidence():
    assert 'chat-readiness' in HTML
    assert 'renderChatReadiness' in CHAT
    assert 'r.ready===true && r.current===true' in CHAT
    assert 'chat-readiness-probe' in CHAT


def test_service_workspace_represents_actual_execution_topology():
    for token in ('svc-gateway-runtime', 'svc-gateway-health', 'svc-agent-status', 'svc-agent-task'):
        assert token in HTML
    assert "$('#svc-start').disabled=!exists" in PANEL
    assert 'Direct Gateway Process' in PANEL


def test_diagnostics_and_structured_evidence_are_separate():
    assert 'Diagnostics خام' in HTML
    assert 'Structured Evidence' in HTML
    assert 'evidence-index' in HTML
    assert "/api/evidence/index" in BACKEND
    assert "api('/evidence/index')" in PANEL


def test_provider_provisioning_does_not_imply_account_was_created():
    assert 'Account Instance هنوز ایجاد نمی‌شود' in HTML
    assert 'Account: هنوز ایجاد نشده' in PANEL
    assert 'حساب‌ها و Session' in PANEL
