from core.blind_discovery import identify_provider, classify_auth_snapshot, compare_blind_to_known, matching_provider_pages


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
    assert classify_auth_snapshot({'login_control':'Sign In','composer':True}).state=='UNKNOWN'
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


def test_shared_cdp_does_not_fall_back_to_other_provider_page():
    class Page:
        def __init__(self, url): self.url=url
    pages=[Page('https://chat.deepseek.com/a/chat/s/1')]
    assert matching_provider_pages(pages,'https://chatgpt.com/') == []
    assert matching_provider_pages(pages,'https://chat.deepseek.com/') == pages


def test_access_semantics_detects_login_expired_without_persisting_payload_data():
    from core.blind_discovery import classify_access_semantic_observations
    s=classify_access_semantic_observations([{
        "endpoint":"/api/v1/userinfo","http_status":200,"code":164003,"message":"login expired"
    }])
    assert s.state=="LOGIN_REQUIRED"
    assert s.user_interaction=="login"
    assert any("164003" in x for x in s.evidence)

def test_access_semantics_remains_unknown_without_auth_failure():
    from core.blind_discovery import classify_access_semantic_observations
    s=classify_access_semantic_observations([{
        "endpoint":"/api/v2/user/quota-usage","http_status":200,"code":100000,"message":"success"
    }])
    assert s.state=="UNKNOWN"
