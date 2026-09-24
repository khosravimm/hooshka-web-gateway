from pathlib import Path
from core.provider_onboarding import synthesize_technical_candidate, apply_submit_qualification


def _analysis():
    return {
        "suggested_provider_id": "future-web",
        "origin": "https://future.example",
        "url": "https://future.example/chat",
        "known_adapter_type": None,
        "recommended_runtime_key": "runtime-1",
    }


def test_login_gate_is_owned_by_user():
    out = synthesize_technical_candidate(
        _analysis(), {"classification": {"state": "login_required"}, "target_id": "T1"}
    )
    assert out["workflow_state"] == "WAITING_FOR_USER_GATE"
    assert out["next_required"] == "user_complete_login_or_verification"
    assert out["user_action_required"] is True


def test_unknown_state_is_owned_by_explorer():
    out = synthesize_technical_candidate(
        _analysis(), {"classification": {"state": "unknown"}, "needs_deeper_exploration": True}
    )
    assert out["workflow_state"] == "EXPLORER_DEEPENING"
    assert out["next_required"] == "autonomous_deeper_exploration"
    assert out["user_action_required"] is False


def test_ready_discovery_builds_uncertified_technical_candidate():
    discovery = {
        "frontend": {
            "composer_selector": "textarea",
            "controls": [{"kind": "model_selector", "selector": "#model", "confidence": "medium"}],
            "upload_surface": {"input_present": True},
        },
        "backend": {"candidate_endpoints": [{"path": "/api/chat"}], "stream_transports": []},
        "capabilities": [{"name": "chat", "supported": True, "evidence": {"type": "E1"}}],
        "behavior_evidence": [],
        "composer_submit_probe": {
            "status": "observed", "marker_sent": False, "composer_restored": True,
            "candidates": [{"selector": "button:nth-of-type(2)", "status": "candidate_unverified"}],
        },
    }
    out = synthesize_technical_candidate(_analysis(), {
        "classification": {"state": "ready"}, "discovery_completed": True,
        "deterministic_discovery": discovery, "target_id": "T2",
    })
    assert out["workflow_state"] == "TECHNICAL_CANDIDATE_READY"
    assert out["status"] == "E1_UNCERTIFIED"
    assert out["next_required"] == "transport_and_behavior_qualification"
    assert out["user_action_required"] is False
    assert out["submit_candidates"][0]["status"] == "candidate_unverified"
    assert out["composer_submit_probe"]["marker_sent"] is False
    assert out["composer_submit_probe"]["composer_restored"] is True


def test_apply_verified_submit_qualification_promotes_only_candidate_control():
    from core.provider_onboarding import apply_submit_qualification
    record = {
        "technical_candidate": {
            "workflow_state": "TECHNICAL_CANDIDATE_READY",
            "status": "E1_UNCERTIFIED",
            "submit_candidates": [
                {"selector": "#send", "status": "candidate_unverified", "confidence": "medium"},
                {"selector": "#other", "status": "candidate_unverified", "confidence": "medium"},
            ],
        }
    }
    result = {"status": "E2_VERIFIED", "submitted": True, "submit_selector": "#send"}
    out = apply_submit_qualification(record, result)
    tc = out["technical_candidate"]
    assert tc["workflow_state"] == "ROUNDTRIP_QUALIFIED"
    assert tc["status"] == "PARTIAL_E2_UNCERTIFIED"
    assert tc["next_required"] == "assistant_surface_discovery"
    assert tc["user_action_required"] is False
    assert tc["submit_candidates"][0]["status"] == "E2_VERIFIED"
    assert tc["submit_candidates"][0]["evidence_level"] == "E2"
    assert tc["submit_candidates"][1]["status"] == "candidate_unverified"


def test_reobserve_preserves_e2_only_for_same_target_and_selector(tmp_path):
    from core.provider_onboarding import save_candidate, candidate_path, apply_submit_qualification
    analysis = _analysis()
    first_observation = {
        "classification": {"state": "ready"}, "discovery_completed": True, "target_id": "T1",
        "deterministic_discovery": {
            "frontend": {"composer_selector": "textarea", "controls": [], "upload_surface": {}},
            "backend": {}, "capabilities": [], "behavior_evidence": [],
            "composer_submit_probe": {"candidates": [{"selector": "#send", "status": "candidate_unverified"}]},
        },
    }
    first = save_candidate(tmp_path, analysis, first_observation)["candidate"]
    first = apply_submit_qualification(first, {"status": "E2_VERIFIED", "submitted": True,
                                                "target_id": "T1", "submit_selector": "#send",
                                                "expected_marker": "HWGQ123"})
    candidate_path(tmp_path, "future-web").write_text(__import__('json').dumps(first), encoding="utf-8")
    same = save_candidate(tmp_path, analysis, first_observation)["candidate"]
    assert same["submit_qualification"]["status"] == "E2_VERIFIED"
    assert same["technical_candidate"]["workflow_state"] == "ROUNDTRIP_QUALIFIED"
    changed = dict(first_observation); changed["target_id"] = "T2"
    fresh = save_candidate(tmp_path, analysis, changed)["candidate"]
    assert "submit_qualification" not in fresh
    assert fresh["technical_candidate"]["workflow_state"] == "TECHNICAL_CANDIDATE_READY"
    assert fresh["qualification_history"]


def test_verified_response_surface_unlocks_adapter_candidate_generation():
    from core.provider_onboarding import apply_submit_qualification
    record={"technical_candidate":{"workflow_state":"TECHNICAL_CANDIDATE_READY","submit_candidates":[{"selector":"#send","status":"candidate_unverified"}]}}
    result={"status":"E2_VERIFIED","submitted":True,"submit_selector":"#send","response_surface":{"status":"E2_VERIFIED","selector":".assistant","strategy":"marker_anchored_dom_surface"}}
    out=apply_submit_qualification(record,result)
    assert out["technical_candidate"]["next_required"]=="adapter_candidate_generation"
    assert out["technical_candidate"]["response_surface"]["selector"]==".assistant"


def test_generate_adapter_candidate_uses_only_recorded_evidence():
    from core.provider_onboarding import generate_adapter_candidate
    record={
      "technical_candidate":{"provider_id":"future-web","origin":"https://future.example","home_url":"https://future.example/chat","runtime_key":"r1","composer_selector":"textarea[placeholder=chat]","response_surface":{"status":"E2_VERIFIED","selector":"div.bot","strategy":"marker_anchored_dom_surface"},"capability_claims":[{"name":"chat","supported":True,"evidence":{"type":"E1","confidence":"high"}},{"name":"streaming","supported":False,"evidence":{"type":"E0","confidence":"low"}}],"upload_surface":{},"backend_hints":{},"unresolved_controls":[]},
      "submit_qualification":{"status":"E2_VERIFIED","submit_selector":"button.send","expected_marker":"HWGQ1","target_id":"T1","response_surface":{"status":"E2_VERIFIED","selector":"div.bot","strategy":"marker_anchored_dom_surface"}}
    }
    adapter=generate_adapter_candidate(record)
    assert adapter["status"]=="GENERATED_UNCERTIFIED"
    assert adapter["transport"]["submit"]["evidence_level"]=="E2"
    assert adapter["transport"]["response"]["selector"]=="div.bot"
    assert record["technical_candidate"]["workflow_state"]=="ADAPTER_CANDIDATE_GENERATED"
    assert record["technical_candidate"]["user_action_required"] is False


def test_materialize_adapter_profile_requires_e2(tmp_path):
    from core.provider_onboarding import materialize_adapter_profile
    record={"candidate_id":"future-web","adapter_candidate":{"status":"GENERATED_UNCERTIFIED"},"adapter_conformance":{"status":"blocked"},"technical_candidate":{}}
    out=materialize_adapter_profile(tmp_path,record)
    assert out["status"]=="blocked"
    assert not (tmp_path/"docs"/"profiles"/"future-web"/"adapter_candidate.v1.json").exists()


def test_materialize_adapter_profile_writes_versioned_candidate(tmp_path):
    from core.provider_onboarding import materialize_adapter_profile
    record={"candidate_id":"future-web","adapter_candidate":{"status":"GENERATED_UNCERTIFIED","provider_id":"future-web"},"adapter_conformance":{"status":"E2_VERIFIED","evidence_level":"E2","expected_marker":"X","provider_meta":{}},"technical_candidate":{}}
    out=materialize_adapter_profile(tmp_path,record)
    assert out["status"]=="E2_CONFORMANT_CANDIDATE"
    assert Path(out["path"]).exists()
    assert record["technical_candidate"]["workflow_state"]=="ADAPTER_PROFILE_MATERIALIZED"


import pytest


class _GateLocator:
    first = None
    def __init__(self):
        self.first = self
        self.fill_calls=[]
    async def count(self): return 1
    async def is_visible(self): return True
    async def input_value(self): return ""
    async def fill(self, value): self.fill_calls.append(value)


class _GatePage:
    def __init__(self): self.loc=_GateLocator()
    def locator(self, _selector): return self.loc


@pytest.mark.asyncio
async def test_composer_probe_stops_before_fill_when_visual_gate_blocks(monkeypatch):
    from core.provider_onboarding import probe_composer_submit_candidates
    import core.visual_discovery as visual
    async def blocked(_page,_action): return {"allowed":False,"classification":{"state":"login_required"}}
    monkeypatch.setattr(visual,"visual_action_gate",blocked)
    page=_GatePage()
    out=await probe_composer_submit_candidates(page,{"frontend":{"composer_selector":"textarea"}})
    assert out["status"]=="blocked"
    assert out["marker_sent"] is False
    assert page.loc.fill_calls==[]

class _GateSession:
    async def send(self,_cmd): return {"targetInfo":{"targetId":"T1"}}
    async def detach(self): return None


class _GateContext:
    def __init__(self,page): self.pages=[page]
    async def new_cdp_session(self,_page): return _GateSession()


class _GateBrowser:
    def __init__(self,page): self.contexts=[_GateContext(page)]


class _GateChromium:
    def __init__(self,page): self.page=page
    async def connect_over_cdp(self,_url): return _GateBrowser(self.page)


class _GatePW:
    def __init__(self,page): self.chromium=_GateChromium(page)
    async def stop(self): return None


class _GatePWFactory:
    def __init__(self,page): self.page=page
    async def start(self): return _GatePW(self.page)

@pytest.mark.asyncio
async def test_submit_qualification_stops_before_prompt_on_visual_block(monkeypatch):
    from core.provider_onboarding import qualify_submit_candidate
    import core.visual_discovery as visual
    import playwright.async_api as pwa
    page=_GatePage()
    async def blocked(_page,_action): return {"allowed":False,"classification":{"state":"challenge"}}
    monkeypatch.setattr(visual,"visual_action_gate",blocked)
    monkeypatch.setattr(pwa,"async_playwright",lambda: _GatePWFactory(page))
    record={"technical_candidate":{"workflow_state":"TECHNICAL_CANDIDATE_READY","target_id":"T1","composer_selector":"textarea","submit_candidates":[{"selector":"#send"}]}}
    out=await qualify_submit_candidate("http://127.0.0.1:9999",record)
    assert out["status"]=="blocked"
    assert out["reason"]=="provider_visual_state"
    assert out["submitted"] is False
    assert out["commitment_state"]=="not_sent"
    assert out["classification"]["state"]=="challenge"
    assert page.loc.fill_calls==[]

def test_observe_url_sync_is_bounded(monkeypatch):
    import asyncio
    import core.provider_onboarding as po
    async def stalled(*args, **kwargs):
        await asyncio.sleep(1)
        return {}
    monkeypatch.setattr(po, "observe_url", stalled)
    try:
        po.observe_url_sync("https://future.example", "http://127.0.0.1:9330", timeout_seconds=0.01)
        assert False, "expected TimeoutError"
    except TimeoutError:
        pass


class _TransitionLocator:
    first = None
    def __init__(self):
        self.first=self
        self.fill_calls=[]
    async def count(self): return 1
    async def is_visible(self): return True
    async def input_value(self): return ""
    async def fill(self,value): self.fill_calls.append(value)
    async def bounding_box(self): return {"x":400,"y":400,"width":800,"height":80}

class _TransitionPage:
    def __init__(self):
        self.loc=_TransitionLocator(); self.eval_calls=0
    def locator(self,_selector): return self.loc
    async def wait_for_timeout(self,_ms): return None
    async def evaluate(self,_script):
        self.eval_calls += 1
        base={"selector":"#send","tag":"BUTTON","role":"","text":"","aria":"","title":"","rect":{"x":1180,"y":420,"w":32,"h":32}}
        if self.eval_calls==1:
            return [{**base,"disabled":True}]
        return [{**base,"disabled":None}]

@pytest.mark.asyncio
async def test_composer_probe_detects_existing_button_enabled_transition(monkeypatch):
    from core.provider_onboarding import probe_composer_submit_candidates
    import core.visual_discovery as visual
    async def allowed(_page,_action): return {"allowed":True,"classification":{"state":"ready"}}
    monkeypatch.setattr(visual,"visual_action_gate",allowed)
    page=_TransitionPage()
    out=await probe_composer_submit_candidates(page,{"frontend":{"composer_selector":"div[contenteditable='true']"}})
    assert out["status"]=="observed"
    assert out["marker_sent"] is False
    assert out["composer_restored"] is True
    assert out["candidates"][0]["selector"]=="#send"
    assert out["candidates"][0]["evidence"]=="becomes_enabled_when_composer_is_temporarily_filled"
    assert page.loc.fill_calls==["HWG_DISCOVERY_PROBE",""]


def test_backend_access_semantics_overrides_visual_ready_for_login_gate():
    out=synthesize_technical_candidate(_analysis(), {
        "classification":{"state":"auth_ambiguous"},
        "access_semantics":{"state":"LOGIN_REQUIRED","confidence":"high","evidence":["message:login expired"]},
        "discovery_completed":True,"target_id":"T1",
        "deterministic_discovery":{"frontend":{"composer_selector":"div[contenteditable='true']","controls":[],"upload_surface":{}},"backend":{},"capabilities":[]},
    })
    assert out["workflow_state"]=="WAITING_FOR_USER_GATE"
    assert out["next_required"]=="user_complete_login_or_verification"
    assert out["user_action_required"] is True
    assert out["access_semantics"]["state"]=="LOGIN_REQUIRED"


def test_response_surface_ephemeral_id_detection():
    from core.provider_onboarding import _is_ephemeral_dom_id
    assert _is_ephemeral_dom_id('f_01234567-89ab-cdef-0123-456789abcdef') is True
    assert _is_ephemeral_dom_id('gpt-message-id-0_1790260644637') is True
    assert _is_ephemeral_dom_id('agent-preview-editor-0-mufmyq80-dn2rs0-block-1-preview') is True
    assert _is_ephemeral_dom_id('chat-scroll-wrapper') is False
    assert _is_ephemeral_dom_id('send-message-button') is False


def test_generate_adapter_candidate_rejects_ephemeral_response_id():
    from core.provider_onboarding import generate_adapter_candidate
    surface={
      "status":"E2_VERIFIED","selector":"#agent-preview-editor-0-mufnfjko-rg06ti-block-1-preview",
      "strategy":"smallest_stable_marker_anchored_surface","exact_marker_text":True,
      "candidates":[
        {"selector":"#agent-preview-editor-0-mufnfjko-rg06ti-block-1-preview","score":49,"exact_marker_text":True},
        {"selector":"div.md-editor-preview.github-theme.md-editor-scrn","score":45,"exact_marker_text":True},
        {"selector":"div.ml-1.mt-3","score":9,"exact_marker_text":False},
      ]}
    record={"technical_candidate":{"provider_id":"future-web","origin":"https://future.example","home_url":"https://future.example","runtime_key":"r1","composer_selector":"div[contenteditable='true']","response_surface":surface,"capability_claims":[],"upload_surface":{},"backend_hints":{},"unresolved_controls":[]},"submit_qualification":{"status":"E2_VERIFIED","submit_selector":"#send","expected_marker":"X","target_id":"T1","response_surface":surface}}
    adapter=generate_adapter_candidate(record)
    response=adapter["transport"]["response"]
    assert response["selector"]=="div.md-editor-preview.github-theme.md-editor-scrn"
    assert response["selectors"][0]==response["selector"]
    assert not any(x.startswith("#agent-preview-editor-0-") for x in response["selectors"])


def test_reobserve_preserves_nonretryable_committed_failure_for_same_target(tmp_path):
    from core.provider_onboarding import save_candidate, candidate_path, apply_submit_qualification
    analysis = _analysis()
    observation = {
        "classification": {"state": "ready"}, "discovery_completed": True, "target_id": "T1",
        "deterministic_discovery": {"frontend": {"composer_selector": "textarea", "controls": [], "upload_surface": {}},
                                    "backend": {}, "capabilities": [], "behavior_evidence": [],
                                    "composer_submit_probe": {"candidates": [{"selector": "#send", "status": "candidate_unverified"}]}}}
    first = save_candidate(tmp_path, analysis, observation)["candidate"]
    first = apply_submit_qualification(first, {"status":"E2_FAILED_AFTER_COMMIT","submitted":True,
        "retry_allowed":False,"target_id":"T1","submit_selector":"#send","expected_marker":"HWGQ999"})
    candidate_path(tmp_path, "future-web").write_text(__import__('json').dumps(first), encoding="utf-8")
    same = save_candidate(tmp_path, analysis, observation)["candidate"]
    assert same["submit_qualification"]["status"] == "E2_FAILED_AFTER_COMMIT"
    assert same["submit_qualification"]["retry_allowed"] is False
    assert same["technical_candidate"]["workflow_state"] == "QUALIFICATION_FAILED_AFTER_COMMIT"
    changed = dict(observation); changed["target_id"] = "T2"
    candidate_path(tmp_path, "future-web").write_text(__import__('json').dumps(first), encoding="utf-8")
    moved = save_candidate(tmp_path, analysis, changed)["candidate"]
    assert moved["submit_qualification"]["status"] == "E2_FAILED_AFTER_COMMIT"
    assert moved["technical_candidate"]["workflow_state"] == "QUALIFICATION_FAILED_AFTER_COMMIT"
