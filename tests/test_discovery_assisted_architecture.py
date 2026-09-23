import json
from pathlib import Path


def _json(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def test_ai_assistance_policy_is_deterministic_first_and_candidate_only():
    p=_json('discovery/policies/ai-assistance-v1.json')
    assert p['deterministic_first'] is True
    assert p['default_mode']=='explicit'
    assert p['output_status']=='CANDIDATE'
    assert p['output_evidence_level']=='E0'
    assert p['direct_profile_mutation'] is False
    assert p['direct_certification'] is False


def test_routing_policy_is_strict_and_does_not_bypass_provider_controls():
    p=_json('discovery/policies/routing-v1.json')
    assert p['exact_route_is_strict'] is True
    assert p['silent_cross_provider_fallback'] is False
    assert p['respect_provider_limits'] is True
    assert p['bypass_challenge_or_suspension'] is False
    assert p['bypass_rate_limit'] is False


def test_assisted_exploration_architecture_is_governed_and_versioned():
    text=Path('docs/governance/HWG_DISCOVERY_ASSISTED_EXPLORATION_ARCHITECTURE_V1.md').read_text(encoding='utf-8-sig')
    assert 'HWG-DISC-AE-001' in text
    assert 'Deterministic Probes' in text
    assert 'Interactive Browser Behavior Lab' in text
    assert 'AI-Assisted Investigator' in text
    assert 'exact-provider' in text or 'Exact-provider' in text


def test_control_plane_requires_confirmation_for_click_and_ai_assistance():
    src=Path('control_panel.py').read_text(encoding='utf-8-sig')
    assert 'Click probes require explicit user confirmation' in src
    assert 'AI assistance requires explicit user approval' in src
    assert '/behavior' in src and '/ai-assist' in src


def test_work_register_tracks_assisted_discovery_and_routing():
    doc=_json('docs/governance/HWG_REMAINING_WORK_REGISTER.json')
    ids={x['id'] for x in doc['items']}
    assert {'HWG-WORK-018','HWG-WORK-019','HWG-WORK-020','HWG-WORK-021','HWG-WORK-022'}.issubset(ids)
    assert doc['version']=='1.33.0'


def test_target_provider_self_use_policy_requires_deterministic_transport_qualification():
    p=_json('discovery/policies/ai-assistance-v1.json')
    gate=p['target_provider_self_use']
    assert gate['user_approval_required'] is True
    assert gate['deterministic_send_path_required'] is True
    assert gate['deterministic_receive_path_required'] is True
    assert gate['deterministic_completion_detection_required'] is True
    assert gate['controlled_roundtrip_required'] is True
    assert gate['transport_fingerprint_must_match'] is True
    assert gate['fail_closed'] is True


def test_control_plane_surfaces_target_self_use_gate():
    src=Path('control_panel.py').read_text(encoding='utf-8-sig')
    js=Path('control_panel_ui/panel.js').read_text(encoding='utf-8-sig')
    assert 'provider_self_use_status' in src
    assert 'runsData.self_use' in js
    assert 'Transport Qualified' in js


def test_self_use_qualification_route_supports_automated_validation():
    src=Path('control_panel.py').read_text(encoding='utf-8-sig')
    js=Path('control_panel_ui/panel.js').read_text(encoding='utf-8-sig')
    assert '/self-use-qualify' in src
    assert 'execution_authority="automated_validation"' in src
    assert 'اجرای آزمون خودکار صلاحیت Self-use' in js
    assert "execution_authority:'automated_validation'" in js


def test_control_plane_surfaces_access_gated_discovery_states():
    js=Path('control_panel_ui/panel.js').read_text(encoding='utf-8-sig')
    for state in ('WAITING_FOR_LOGIN','WAITING_FOR_USER_INTERACTION','DIAGNOSTIC_REQUIRED','BLOCKED'):
        assert state in js
    assert 'بررسی مجدد وضعیت دسترسی' in js
    assert 'resolve_access_then_rebaseline' in Path('control_panel.py').read_text(encoding='utf-8-sig')


def test_control_plane_exposes_automated_e2_certification_path():
    src=Path('control_panel.py').read_text(encoding='utf-8-sig')
    js=Path('control_panel_ui/panel.js').read_text(encoding='utf-8-sig')
    assert '/certification/auto' in src
    assert 'controlled_self_use_roundtrip' in src
    assert 'execution_authority="automated_validation"' in src
    assert 'اجرای Certification خودکار / E2' in js
    assert "endpoint = 'certification/auto'" in js
