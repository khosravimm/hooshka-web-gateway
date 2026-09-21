from flask import Flask
import control_panel


def _client():
    app = Flask(__name__)
    app.register_blueprint(control_panel.control_panel_bp)
    app.testing = True
    return app.test_client()


def _runtime():
    return {
        "runtime_key": "http://127.0.0.1:9330|.runtime-dev\\shared-profile",
        "cdp_url": "http://127.0.0.1:9330",
        "profile": ".runtime-dev\\shared-profile",
        "port": 9330,
        "providers": [],
        "provider_count": 0,
        "shared": True,
    }


def test_provider_post_uses_canonical_top_level_runtime(monkeypatch):
    cfg = {"providers": []}
    saved = {}
    monkeypatch.setattr(control_panel, "_browser_runtime_groups", lambda: [_runtime()])
    monkeypatch.setattr(control_panel, "_load_config_file", lambda: cfg)
    monkeypatch.setattr(control_panel, "_save_config_file", lambda value: saved.update(value))
    monkeypatch.setattr(control_panel, "_sync_auth_keys", lambda: None)
    monkeypatch.setattr(control_panel, "_schedule_restart_all", lambda reason: {"scheduled": True})
    resp = _client().post('/panel/api/providers', json={
        "id": "deepseek-office", "type": "deepseek_web",
        "runtime_key": _runtime()["runtime_key"], "priority": 55,
    })
    assert resp.status_code == 201
    item = cfg["providers"][0]
    assert item["enabled"] is False
    assert item["runtime"]["cdp_url"].endswith(":9330")
    assert item["runtime"]["profile_dir"].endswith("shared-profile")
    assert "runtime" not in item["config"]
    assert item["config"]["cdp_url"].endswith(":9330")
    assert item["config"]["base_url"] == "https://chat.deepseek.com/"


def test_provider_post_rejects_unknown_runtime(monkeypatch):
    monkeypatch.setattr(control_panel, "_browser_runtime_groups", lambda: [])
    resp = _client().post('/panel/api/providers', json={
        "id": "zai-office", "type": "zai_web", "runtime_key": "missing"
    })
    assert resp.status_code == 400
    assert resp.get_json()["error"] == "existing browser runtime selection is required"


def test_provider_form_uses_relationship_workflow_not_raw_cdp_fields():
    html = open('control_panel_ui/index.html', encoding='utf-8').read()
    js = open('control_panel_ui/panel.js', encoding='utf-8').read()
    assert 'id="pf-runtime"' in html
    assert 'id="pf-cdp"' not in html
    assert 'id="pf-profile"' not in html
    assert '<select id="pf-type"' in html
    assert 'Provider → Browser Runtime' not in html  # preview is generated dynamically
    assert "runtime_key: $('#pf-runtime').value" in js
    assert "api('/browser-runtimes')" in js
    assert "config: {\n          runtime:" not in js
