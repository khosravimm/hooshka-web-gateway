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
    monkeypatch.setattr(control_panel, 'observe_url_sync', lambda url,cdp,preferred_target_id=None,candidate_id=None:{'title':'Future','classification':{'state':'ready'},'interaction_summary':{'controls':4},'target_id':'T1'})
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


def test_provider_wizard_unknown_is_owned_by_explorer_not_user():
    src=open('core/provider_onboarding.py',encoding='utf-8').read()
    ui=open('control_panel_ui/panel.js',encoding='utf-8').read()
    assert 'needs_deeper_exploration' in src
    assert 'فعلاً اقدامی از شما لازم نیست' in ui


def test_provider_wizard_forwards_page_identity(monkeypatch):
    runtime=_runtime(); runtime['ready']=True
    monkeypatch.setattr(control_panel, '_browser_runtime_groups', lambda:[runtime])
    monkeypatch.setattr(control_panel.provider_registry, 'list_providers', lambda enabled_only=False:[])
    seen={}
    def observe(url,cdp,preferred_target_id=None,candidate_id=None):
        seen.update(preferred=preferred_target_id,candidate=candidate_id)
        return {'classification':{'state':'ready'},'target_id':'T1'}
    monkeypatch.setattr(control_panel,'observe_url_sync',observe)
    monkeypatch.setattr(control_panel,'save_candidate',lambda root,a,o:{'candidate':{'state':'OBSERVED'},'record':'x'})
    resp=_client().post('/panel/api/provider-wizard/observe',json={'url':'https://future.example/chat','runtime_key':runtime['runtime_key'],'preferred_target_id':'ABC'})
    assert resp.status_code==200
    assert seen=={'preferred':'ABC','candidate':'future-web'}


def test_provider_wizard_qualification_reuses_existing_e2(monkeypatch):
    runtime = _runtime(); runtime["ready"] = True
    record = {"candidate_id": "future-web", "analysis": {"recommended_runtime_key": runtime["runtime_key"]},
              "submit_qualification": {"status": "E2_VERIFIED", "submit_selector": "#send"}}
    monkeypatch.setattr(control_panel, "load_candidate", lambda root, cid: record)
    called = {"qualify": 0}
    monkeypatch.setattr(control_panel, "qualify_submit_candidate_sync", lambda *a, **k: called.__setitem__("qualify", called["qualify"] + 1))
    resp = _client().post('/panel/api/provider-wizard/qualify/future-web', json={})
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["qualification"]["status"] == "E2_VERIFIED"
    assert body["qualification"]["reused_evidence"] is True
    assert called["qualify"] == 0


def test_provider_wizard_qualification_persists_success(monkeypatch, tmp_path):
    runtime = _runtime(); runtime["ready"] = True
    record = {"candidate_id": "future-web", "analysis": {"recommended_runtime_key": runtime["runtime_key"]},
              "technical_candidate": {"workflow_state": "TECHNICAL_CANDIDATE_READY", "submit_candidates": [{"selector": "#send", "status": "candidate_unverified"}]}}
    monkeypatch.setattr(control_panel, "load_candidate", lambda root, cid: record)
    monkeypatch.setattr(control_panel, "_browser_runtime_by_key", lambda key: runtime)
    monkeypatch.setattr(control_panel, "qualify_submit_candidate_sync", lambda *a, **k: {"status": "E2_VERIFIED", "submitted": True, "submit_selector": "#send", "response_verified": True})
    saved = {}
    monkeypatch.setattr(control_panel, "persist_candidate", lambda root, rec: saved.setdefault("record", rec) or tmp_path / "x.json")
    resp = _client().post('/panel/api/provider-wizard/qualify/future-web', json={})
    assert resp.status_code == 200
    assert resp.get_json()["qualification"]["response_verified"] is True
    assert record["technical_candidate"]["workflow_state"] == "ROUNDTRIP_QUALIFIED"


def test_provider_wizard_ui_runs_qualification_without_user_config_input():
    html = open('control_panel_ui/index.html', encoding='utf-8').read()
    js = open('control_panel_ui/panel.js', encoding='utf-8').read()
    assert 'autoQualifyWizardCandidate' in js
    assert "/provider-wizard/qualify/" in js
    assert 'TECHNICAL_CANDIDATE_READY' in js
    assert 'ROUNDTRIP_QUALIFIED' in js
    assert 'فعلاً اقدامی از شما لازم نیست' in js
    assert 'لازم نیست خودتان پیام آزمایشی بفرستید' in html
    assert 'یک پیام مصنوعی کوتاه' in html


def test_discovered_candidate_registration_requires_e2(monkeypatch):
    record={"candidate_id":"future-web","technical_candidate":{},
            "adapter_conformance":{"status":"E2_REFINEMENT_REQUIRED"},
            "materialized_adapter_profile":{"status":"E2_CONFORMANT_CANDIDATE","path":"ignored.json"}}
    monkeypatch.setattr(control_panel,"load_candidate",lambda root,cid:record)
    resp=_client().post('/panel/api/provider-wizard/register/future-web',json={})
    assert resp.status_code==409
    assert resp.get_json()["error"]=="adapter_conformance_e2_required"


def test_discovered_candidate_registers_disabled_from_materialized_profile(monkeypatch,tmp_path):
    monkeypatch.setattr(control_panel,"__file__",str(tmp_path/'control_panel.py'))
    folder=tmp_path/'docs'/'profiles'/'future-web'; folder.mkdir(parents=True)
    profile=folder/'adapter_candidate.v1.json'
    profile.write_text('{"status":"E2_CONFORMANT_CANDIDATE","provider_id":"future-web","adapter_candidate":{"home_url":"https://future.example/chat"}}',encoding='utf-8')
    runtime=_runtime(); runtime['ready']=True
    record={"candidate_id":"future-web","analysis":{"url":"https://future.example/chat","recommended_runtime_key":runtime['runtime_key']},
            "technical_candidate":{},"adapter_conformance":{"status":"E2_VERIFIED"},
            "materialized_adapter_profile":{"status":"E2_CONFORMANT_CANDIDATE","path":str(profile)}}
    cfg={"providers":[]}; saved={}
    monkeypatch.setattr(control_panel,"load_candidate",lambda root,cid:record)
    monkeypatch.setattr(control_panel,"_browser_runtime_by_key",lambda key:runtime)
    monkeypatch.setattr(control_panel,"_load_config_file",lambda:cfg)
    monkeypatch.setattr(control_panel,"_save_config_file",lambda value:saved.update(value))
    monkeypatch.setattr(control_panel,"_sync_auth_keys",lambda:None)
    monkeypatch.setattr(control_panel,"_schedule_restart_all",lambda reason:{"scheduled":True})
    monkeypatch.setattr(control_panel,"persist_candidate",lambda root,rec:profile)
    resp=_client().post('/panel/api/provider-wizard/register/future-web',json={})
    assert resp.status_code==201
    item=cfg['providers'][0]
    assert item['type']=='custom'
    assert item['enabled'] is False
    assert item['config']['adapter_kind']=='discovered_web'
    assert item['config']['adapter_profile_path']=='docs/profiles/future-web/adapter_candidate.v1.json'
    assert record['technical_candidate']['workflow_state']=='DISABLED_PROVIDER_REGISTERED'
    assert record['technical_candidate']['next_required']=='readiness_probe_before_enable'


def test_advance_reconciles_stale_readiness_before_enable(monkeypatch,tmp_path):
    runtime=_runtime(); runtime['ready']=True
    record={
        'candidate_id':'future-web',
        'analysis':{'recommended_runtime_key':runtime['runtime_key']},
        'technical_candidate':{
            'workflow_state':'READY_FOR_ENABLE_CONFIRMATION',
            'next_required':'explicit_enable_confirmation',
            'user_action_required':True,
        },
    }
    monkeypatch.setattr(control_panel,'load_candidate',lambda root,cid:record)
    monkeypatch.setattr(control_panel,'_browser_runtime_by_key',lambda key:runtime)
    monkeypatch.setattr(control_panel,'load_readiness',lambda provider_id:{'state':'READY','ready':True,'current':False,'checked_at':'old','expires_at_epoch':1})
    monkeypatch.setattr(control_panel,'persist_candidate',lambda root,rec:tmp_path/'candidate.json')
    resp=_client().post('/panel/api/provider-wizard/advance/future-web',json={})
    assert resp.status_code==200
    body=resp.get_json()
    assert body['workflow_state']=='DISABLED_PROVIDER_REGISTERED'
    assert body['next_required']=='readiness_probe_before_enable'
    assert record['technical_candidate']['user_action_required'] is False
    assert record['readiness']['current'] is False


def test_readiness_sync_requires_current_evidence():
    source=open('control_panel.py',encoding='utf-8').read()
    assert 'current_record.get("current") is True' in source
