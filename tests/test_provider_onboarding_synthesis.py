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
