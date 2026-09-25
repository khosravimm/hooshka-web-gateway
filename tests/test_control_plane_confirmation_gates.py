from pathlib import Path

import control_panel
from main import create_app

ROOT = Path(__file__).resolve().parents[1]

def _client():
    app = create_app()
    app.config.update(TESTING=True)
    return app.test_client()

def test_destructive_control_plane_routes_require_confirmation(monkeypatch):
    cfg={"providers":[{"id":"deepseek-web","enabled":True}],"governance":{"auth":{"enabled":False,"api_keys":{"ref1":"user"}}}}
    monkeypatch.setattr(control_panel, '_load_config_file', lambda: cfg)
    monkeypatch.setattr(control_panel, '_save_config_file', lambda value: (_ for _ in ()).throw(AssertionError('must not persist without confirmation')))
    c=_client()
    assert c.delete('/panel/api/providers/deepseek-web').status_code == 400
    assert c.post('/panel/api/auth/keys', json={}).status_code == 400
    assert c.delete('/panel/api/auth/keys/ref1').status_code == 400
    assert c.post('/panel/api/auth/settings', json={"enabled":True}).status_code == 400

def test_discovery_review_requires_explicit_confirmation(monkeypatch):
    called=[]
    monkeypatch.setattr(control_panel, 'load_discovery_run', lambda provider, run: called.append((provider,run)))
    c=_client()
    r=c.post('/panel/api/discovery/runs/deepseek-web/run-1/review', json={"decision":"ACCEPT"})
    assert r.status_code == 400
    assert r.get_json()['error'] == 'confirmation_required'
    assert called == []

def test_panel_ui_sends_confirmation_for_sensitive_actions():
    js=(ROOT/'control_panel_ui'/'panel.js').read_text(encoding='utf-8-sig')
    assert "JSON.stringify({confirm:true})" in js
    assert "JSON.stringify({ enabled, confirm:true })" in js
    assert "confirmed_by_user:true" in js
    assert "if (!confirm('تصمیم ' + decision" in js
