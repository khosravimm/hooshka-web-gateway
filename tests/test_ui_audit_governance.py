import json
from pathlib import Path


def test_ui_audit_framework_and_register_are_governed():
    framework = Path('docs/governance/HWG_MISSION_DRIVEN_UI_AUDIT_FRAMEWORK.md').read_text(encoding='utf-8')
    reg = json.loads(Path('docs/governance/HWG_UI_UX_AUDIT_REGISTER.json').read_text(encoding='utf-8'))
    assert 'HWG-UI-AUDIT-001' in framework
    assert reg['id'] == 'HWG-UI-AUDIT-REGISTER-001'
    assert reg['work_item'] == 'HWG-WORK-025'
    assert reg['summary']['workspace_count'] >= 16
    assert reg['summary']['p0_open'] == 0


def test_ui_audit_core_semantics_are_preserved():
    index = Path('control_panel_ui/index.html').read_text(encoding='utf-8')
    js = Path('control_panel_ui/panel.js').read_text(encoding='utf-8')
    assert 'providers-grid' in index and 'providers-body' not in index
    assert 'cfg-cdp-url' not in index
    assert 'repair-all-runtimes' not in index
    assert 'نقشه اجرای Discovery' in index
    assert 'Automated E2' in index and 'Human Acceptance' in index
    assert 'ذهن اجرایی MCP' not in index
    assert 'STALE · Probe لازم' in js
    assert 'cfg-provider-enabled-' not in js and 'cfg-provider-cdp-' not in js
