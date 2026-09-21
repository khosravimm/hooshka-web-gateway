from core.blind_discovery import identify_provider, classify_auth_snapshot, compare_blind_to_known


def test_provider_identity_from_host_without_profile():
    assert identify_provider('https://chat.deepseek.com/a/chat/s/1').provider_id == 'deepseek-web'
    assert identify_provider('https://chatgpt.com/').provider_id == 'chatgpt-web'
    assert identify_provider('https://chat.qwen.ai/').provider_id == 'qwen-web'
    assert identify_provider('https://chat.z.ai/').provider_id == 'zai-web'


def test_auth_classifier_prefers_challenge_over_composer():
    s=classify_auth_snapshot({'composer':True,'challenge_visible':True})
    assert s.state=='USER_INTERACTION_REQUIRED'
    assert s.user_interaction=='challenge_or_verification'


def test_auth_classifier_detects_login_without_transcript_text():
    assert classify_auth_snapshot({'password_input':True}).state=='LOGIN_REQUIRED'
    assert classify_auth_snapshot({'login_control':'Sign in','composer':False}).state=='LOGIN_REQUIRED'
    assert classify_auth_snapshot({'composer':True}).state=='AUTHENTICATED'
    assert classify_auth_snapshot({}).state=='UNKNOWN'


def test_auth_classifier_detects_provider_region_restriction():
    s=classify_auth_snapshot({'provider_restriction':'region_restriction','composer':False})
    assert s.state=='BLOCKED'
    assert s.block_reason=='region_restriction'
    assert s.user_interaction is None


def test_compare_blind_to_known_reports_match_missed_new():
    blind={'frontend':{'controls':[{'kind':'send'},{'kind':'search_toggle'}]},'backend':{'candidate_endpoints':[{'path':'/api/chat'},{'path':'/api/new'}]}}
    known={'frontend':{'controls':[{'kind':'send'},{'kind':'thinking_toggle'}]},'backend':{'candidate_endpoints':[{'path':'/api/chat'},{'path':'/api/old'}]}}
    c=compare_blind_to_known(blind,known)
    assert c['controls']['match']==['send']
    assert c['controls']['missed']==['thinking_toggle']
    assert c['controls']['new']==['search_toggle']
    assert c['endpoints']['match']==['/api/chat']
    assert c['endpoints']['missed']==['/api/old']
    assert c['endpoints']['new']==['/api/new']
