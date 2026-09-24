from core.discovery_ai_blocker import _normalize_steps, build_blocker_evidence, verify_ai_blocker_plan


def test_blocker_ai_plan_separates_safe_and_gated_actions():
    safe,gated=_normalize_steps([
        {'kind':'inspect_recorded_network','confidence':'high'},
        {'kind':'resend_probe','confidence':'medium'},
        {'kind':'click','confidence':'low'},
        {'kind':'invented_action','confidence':'high'},
    ])
    assert [x['kind'] for x in safe]==['inspect_recorded_network']
    assert [x['kind'] for x in gated]==['resend_probe','click']


def test_blocker_evidence_keeps_prior_e2_without_promoting_current_state():
    record={'candidate_id':'x','technical_candidate':{'workflow_state':'QUALIFICATION_DIAGNOSIS_COMPLETE'},'qualification_history':[{'status':'E2_VERIFIED','expected_marker':'old'},{'status':'E2_FAILED_AFTER_COMMIT'}]}
    e=build_blocker_evidence(record)
    assert e['workflow_state']=='QUALIFICATION_DIAGNOSIS_COMPLETE'
    assert e['prior_e2_verified_attempts'][0]['expected_marker']=='old'



def test_ai_blocker_verifier_accepts_transport_marker_without_resend(monkeypatch):
    import core.provider_onboarding as onboarding
    monkeypatch.setattr(onboarding,'diagnose_committed_qualification_sync',lambda cdp,record:{'status':'E2_DIAGNOSED','marker_found':False})
    record={'submit_qualification':{'status':'E2_FAILED_AFTER_COMMIT','network_responses':[{'status':200,'expected_marker_found':True}],'transport_marker_found':True},'qualification_history':[]}
    diagnosis={'auto_safe_steps':[{'kind':'inspect_recorded_network'}],'approval_required_steps':[{'kind':'resend_probe'}]}
    out=verify_ai_blocker_plan('http://cdp',record,diagnosis)
    assert out['status']=='E2_TRANSPORT_MARKER_VERIFIED'
    assert out['transport_marker_found'] is True


def test_ai_blocker_verifier_escalates_to_human_gate_after_safe_checks(monkeypatch):
    import core.provider_onboarding as onboarding
    monkeypatch.setattr(onboarding,'diagnose_committed_qualification_sync',lambda cdp,record:{'status':'E2_DIAGNOSED','marker_found':False})
    record={'submit_qualification':{'status':'E2_FAILED_AFTER_COMMIT'},'qualification_history':[]}
    diagnosis={'auto_safe_steps':[{'kind':'inspect_current_dom'}],'approval_required_steps':[{'kind':'resend_probe'}]}
    out=verify_ai_blocker_plan('http://cdp',record,diagnosis)
    assert out['status']=='HUMAN_GATE_REQUIRED'
    assert out['next_required']=='approve_new_instrumented_probe'
