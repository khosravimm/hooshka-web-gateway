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


def test_provider_form_is_url_driven_guided_discovery():
    html = open('control_panel_ui/index.html', encoding='utf-8').read()
    js = open('control_panel_ui/panel.js', encoding='utf-8').read()
    assert 'id="pf-url"' in html
    assert 'id="pf-analyze"' in html
    assert 'id="pf-observe"' in html
    assert 'id="pf-runtime"' in html
    assert 'id="pf-type"' not in html
    assert 'id="pf-id"' not in html
    assert 'id="pf-priority"' not in html
    assert "api('/provider-wizard/analyze'" in js
    assert "api('/provider-wizard/observe'" in js
    assert 'فقط آدرس وب‌چت را وارد کنید' in html


def test_provider_wizard_analyzes_known_and_unknown_urls(monkeypatch):
    runtime=_runtime(); runtime['ready']=True
    monkeypatch.setattr(control_panel, '_browser_runtime_groups', lambda:[runtime])
    monkeypatch.setattr(control_panel.provider_registry, 'list_providers', lambda enabled_only=False:[])
    client=_client()
    known=client.post('/panel/api/provider-wizard/analyze',json={'url':'https://chat.deepseek.com/a/chat'})
    assert known.status_code==200
    assert known.get_json()['known_adapter_type']=='deepseek_web'
    unknown=client.post('/panel/api/provider-wizard/analyze',json={'url':'https://future.example/chat'})
    assert unknown.status_code==200
    assert unknown.get_json()['recommendation']=='discovery_candidate'
    assert unknown.get_json()['known_adapter_type'] is None


def test_provider_wizard_observation_persists_candidate(monkeypatch):
    runtime=_runtime(); runtime['ready']=True
    monkeypatch.setattr(control_panel, '_browser_runtime_groups', lambda:[runtime])
    monkeypatch.setattr(control_panel.provider_registry, 'list_providers', lambda enabled_only=False:[])
    monkeypatch.setattr(control_panel, 'observe_url_sync', lambda url,cdp:{'title':'Future','classification':{'state':'ready'},'interaction_summary':{'controls':4}})
    monkeypatch.setattr(control_panel, 'save_candidate', lambda root,a,o:{'candidate':{'candidate_id':a['suggested_provider_id'],'state':'OBSERVED'},'record':'candidate.json'})
    resp=_client().post('/panel/api/provider-wizard/observe',json={'url':'https://future.example/chat','runtime_key':runtime['runtime_key']})
    assert resp.status_code==200
    body=resp.get_json()
    assert body['candidate']['state']=='OBSERVED'
    assert body['observation']['classification']['state']=='ready'


def test_provider_wizard_prefers_existing_provider_for_same_origin(monkeypatch):
    runtime=_runtime(); runtime['ready']=True; runtime['providers']=[{'id':'deepseek-web','home_url':'https://chat.deepseek.com/'}]
    monkeypatch.setattr(control_panel, '_browser_runtime_groups', lambda:[runtime])
    monkeypatch.setattr(control_panel.provider_registry, 'list_providers', lambda enabled_only=False:[])
    body=_client().post('/panel/api/provider-wizard/analyze',json={'url':'https://chat.deepseek.com/a/chat'}).get_json()
    assert body['recommendation']=='use_existing_provider'
    assert body['register_new_provider'] is False
    assert body['existing_origin_provider_ids']==['deepseek-web']


def test_provider_wizard_suggests_meaningful_name_from_chat_subdomain(monkeypatch):
    runtime=_runtime(); runtime['ready']=True
    monkeypatch.setattr(control_panel, '_browser_runtime_groups', lambda:[runtime])
    monkeypatch.setattr(control_panel.provider_registry, 'list_providers', lambda enabled_only=False:[])
    body=_client().post('/panel/api/provider-wizard/analyze',json={'url':'https://chat.mistral.ai/chat'}).get_json()
    assert body['suggested_name']=='Mistral'
    assert body['suggested_provider_id']=='mistral-web'
