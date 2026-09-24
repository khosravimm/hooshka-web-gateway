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


def test_provider_wizard_ai_assist_requires_explicit_approval():
    resp=_client().post('/panel/api/provider-wizard/ai-assist/future-web',json={})
    assert resp.status_code==400
    assert resp.get_json()['error']=='user_approval_required'


def test_provider_wizard_ai_assist_missing_candidate(monkeypatch):
    monkeypatch.setattr(control_panel,'load_candidate',lambda root,cid: (_ for _ in ()).throw(FileNotFoundError(cid)))
    resp=_client().post('/panel/api/provider-wizard/ai-assist/missing',json={'confirmed_by_user':True})
    assert resp.status_code==404
    assert resp.get_json()['error']=='candidate_not_found'


def test_provider_wizard_visual_ai_fails_closed_without_trusted_screenshot(monkeypatch):
    record={
        'candidate_id':'future-web',
        'technical_candidate':{'unresolved_controls':[{'control_id':'u1','selector':'#u1'}]},
        'observation':{'exploration_trace':[]},
    }
    monkeypatch.setattr(control_panel,'load_candidate',lambda root,cid:record)
    resp=_client().post('/panel/api/provider-wizard/ai-assist/future-web',json={'confirmed_by_user':True,'include_visual_evidence':True})
    assert resp.status_code==409
    assert resp.get_json()['error']=='visual_evidence_unavailable'


def test_provider_wizard_observation_timeout_is_explicit(monkeypatch):
    runtime=_runtime(); runtime['ready']=True
    monkeypatch.setattr(control_panel, '_browser_runtime_groups', lambda:[runtime])
    monkeypatch.setattr(control_panel.provider_registry, 'list_providers', lambda enabled_only=False:[])
    def timeout(*args, **kwargs):
        raise TimeoutError('bounded observation timeout')
    monkeypatch.setattr(control_panel, 'observe_url_sync', timeout)
    resp=_client().post('/panel/api/provider-wizard/observe',json={'url':'https://future.example/chat','runtime_key':runtime['runtime_key']})
    assert resp.status_code==504
    assert resp.get_json()['error']=='provider_observation_timeout'


def test_provider_wizard_exposes_persistent_working_state():
    html = open('control_panel_ui/index.html', encoding='utf-8').read()
    js = open('control_panel_ui/panel.js', encoding='utf-8').read()
    css = open('control_panel_ui/panel.css', encoding='utf-8').read()
    assert 'id="pf-activity"' in html
    assert 'id="pf-activity-stage"' in html
    assert 'id="pf-activity-elapsed"' in html
    assert 'aria-live="polite"' in html
    assert 'beginWizardActivity' in js
    assert 'updateWizardActivity' in js
    assert 'endWizardActivity' in js
    assert 'مرحله ۲ از ۳ — مشاهده واقعی صفحه' in js
    assert 'مرحله ۳ از ۳ — Qualification رفتاری E2' in js
    assert '.wizard-spinner' in css
    assert '.wizard-progress' in css


def test_provider_wizard_qualification_domain_failure_returns_http_200(monkeypatch, tmp_path):
    runtime = _runtime(); runtime["ready"] = True
    record = {"candidate_id": "future-web", "analysis": {"recommended_runtime_key": runtime["runtime_key"]},
              "technical_candidate": {"workflow_state": "TECHNICAL_CANDIDATE_READY", "submit_candidates": [{"selector": "#send"}]}}
    monkeypatch.setattr(control_panel, "load_candidate", lambda root, cid: record)
    monkeypatch.setattr(control_panel, "_browser_runtime_by_key", lambda key: runtime)
    monkeypatch.setattr(control_panel, "qualify_submit_candidate_sync", lambda *a, **k: {
        "status": "E2_FAILED_AFTER_COMMIT", "submitted": True, "retry_allowed": False,
        "response_verified": False, "reason": "response_not_verified"})
    monkeypatch.setattr(control_panel, "persist_candidate", lambda root, rec: tmp_path / "future-web.json")
    resp = _client().post('/panel/api/provider-wizard/qualify/future-web', json={})
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["qualification"]["status"] == "E2_FAILED_AFTER_COMMIT"
    assert body["qualification"]["retry_allowed"] is False


def test_provider_wizard_ui_explains_failed_after_commit_without_http_code():
    js = open('control_panel_ui/panel.js', encoding='utf-8').read()
    assert "qr.status==='E2_FAILED_AFTER_COMMIT'" in js
    assert 'retry خودکار انجام نمی‌دهد' in js


def test_provider_wizard_ui_surfaces_nonretryable_qualification_lock():
    js = open('control_panel_ui/panel.js', encoding='utf-8').read()
    assert "tc.workflow_state==='QUALIFICATION_FAILED_AFTER_COMMIT'" in js
    assert 'تشخیص پس از commit — بدون ارسال مجدد' in js


def test_provider_wizard_diagnoses_committed_failure_without_retry(monkeypatch, tmp_path):
    runtime=_runtime(); runtime['ready']=True
    record={'candidate_id':'future-web','analysis':{'recommended_runtime_key':runtime['runtime_key']},'technical_candidate':{'workflow_state':'QUALIFICATION_FAILED_AFTER_COMMIT'},'submit_qualification':{'status':'E2_FAILED_AFTER_COMMIT','submitted':True,'retry_allowed':False}}
    monkeypatch.setattr(control_panel,'load_candidate',lambda root,cid:record)
    monkeypatch.setattr(control_panel,'_browser_runtime_by_key',lambda key:runtime)
    monkeypatch.setattr(control_panel,'diagnose_committed_qualification_sync',lambda *a,**k:{'status':'E2_DIAGNOSED','marker_found':False,'retry_allowed':False,'result':'marker_not_present_in_current_dom'})
    monkeypatch.setattr(control_panel,'persist_candidate',lambda root,rec:tmp_path/'candidate.json')
    resp=_client().post('/panel/api/provider-wizard/diagnose/future-web',json={'runtime_key':runtime['runtime_key']})
    assert resp.status_code==200
    body=resp.get_json()
    assert body['diagnosis']['status']=='E2_DIAGNOSED'
    assert body['candidate']['technical_candidate']['workflow_state']=='QUALIFICATION_DIAGNOSIS_COMPLETE'
    assert body['candidate']['technical_candidate']['next_required']=='response_transport_analysis_without_resend'


def test_provider_wizard_ui_has_real_committed_failure_diagnosis_step():
    js=open('control_panel_ui/panel.js',encoding='utf-8').read()
    assert "/provider-wizard/diagnose/" in js
    assert 'تشخیص پس از commit — بدون ارسال مجدد' in js
    assert 'QUALIFICATION_DIAGNOSIS_COMPLETE' in js


def test_provider_wizard_integrated_live_view_contract():
    html=open('control_panel_ui/index.html',encoding='utf-8').read()
    css=open('control_panel_ui/panel.css',encoding='utf-8').read()
    js=open('control_panel_ui/panel.js',encoding='utf-8').read()
    assert 'id="pf-live-pane"' in html and 'id="pf-live-image"' in html
    assert 'provider-explorer-workspace' in css
    assert "/provider-wizard/open-target" in js
    assert "/provider-wizard/live-view" in js
    assert "/provider-wizard/live-input" in js
    assert 'startProviderLiveView' in js


def test_provider_wizard_open_target_uses_selected_runtime(monkeypatch):
    runtime=_runtime(); runtime['ready']=True
    monkeypatch.setattr(control_panel,'_browser_runtime_by_key',lambda key:runtime)
    monkeypatch.setattr(control_panel,'open_target_sync',lambda cdp,url:{'target_id':'T-LIVE','url':url,'title':'Live'})
    resp=_client().post('/panel/api/provider-wizard/open-target',json={'runtime_key':runtime['runtime_key'],'url':'https://future.example/chat'})
    assert resp.status_code==200
    assert resp.get_json()['target_id']=='T-LIVE'


def test_provider_wizard_live_input_blocks_sensitive_result(monkeypatch):
    runtime=_runtime(); runtime['ready']=True
    monkeypatch.setattr(control_panel,'_browser_runtime_by_key',lambda key:runtime)
    monkeypatch.setattr(control_panel,'dispatch_live_input_sync',lambda cdp,data:{'status':'blocked','reason':'sensitive_input_requires_native_tab'})
    resp=_client().post('/panel/api/provider-wizard/live-input',json={'runtime_key':runtime['runtime_key'],'kind':'text','text':'secret'})
    assert resp.status_code==409
    assert resp.get_json()['reason']=='sensitive_input_requires_native_tab'


def test_sidebar_meta_is_compact_and_has_no_evidence_dump():
    html=open('control_panel_ui/index.html',encoding='utf-8').read()
    js=open('control_panel_ui/panel.js',encoding='utf-8').read()
    assert 'id="meta-version"' in html
    assert 'id="meta-build"' in html
    assert 'id="meta-evidence"' not in html
    assert 'id="meta-ui"' not in html
    assert "$('#meta-evidence')" not in js
    assert "$('#meta-ui')" not in js


def test_provider_wizard_close_target_is_owned_only(monkeypatch):
    runtime=_runtime(); runtime['ready']=True
    monkeypatch.setattr(control_panel,'_browser_runtime_by_key',lambda key:runtime)
    monkeypatch.setattr(control_panel,'close_owned_target_sync',lambda cdp,target_id:{'status':'closed','target_id':target_id})
    resp=_client().post('/panel/api/provider-wizard/close-target',json={'runtime_key':runtime['runtime_key'],'target_id':'T-LIVE'})
    assert resp.status_code==200
    assert resp.get_json()['status']=='closed'


def test_provider_wizard_screencast_routes(monkeypatch):
    runtime=_runtime(); runtime['ready']=True
    monkeypatch.setattr(control_panel,'_browser_runtime_by_key',lambda key:runtime)
    monkeypatch.setattr(control_panel,'start_screencast_sync',lambda cdp,target_id,url='':{'status':'starting','target_id':target_id})
    monkeypatch.setattr(control_panel,'get_screencast_frame',lambda cdp,target_id:{'status':'streaming','target_id':target_id,'sequence':7,'frame':b'jpg','metadata':{'deviceWidth':1280,'deviceHeight':720}})
    monkeypatch.setattr(control_panel,'stop_screencast_sync',lambda cdp,target_id:{'status':'stopped','target_id':target_id,'sequence':7})
    c=_client(); payload={'runtime_key':runtime['runtime_key'],'target_id':'T-SC','url':'https://future.example/chat'}
    assert c.post('/panel/api/provider-wizard/screencast/start',json=payload).status_code==200
    frame=c.get('/panel/api/provider-wizard/screencast/frame',query_string={'runtime_key':runtime['runtime_key'],'target_id':'T-SC'})
    assert frame.status_code==200 and frame.data==b'jpg'
    assert frame.headers['X-HWG-Sequence']=='7'
    assert frame.headers['X-HWG-Viewport-Width']=='1280'
    assert c.post('/panel/api/provider-wizard/screencast/stop',json=payload).status_code==200


def test_integrated_workspace_prefers_cdp_screencast():
    js=open('control_panel_ui/panel.js',encoding='utf-8').read()
    assert '/provider-wizard/screencast/start' in js
    assert '/provider-wizard/screencast/frame' in js
    assert '/provider-wizard/screencast/stop' in js
    assert 'setInterval(pollProviderLiveView,250)' in js
