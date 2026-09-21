from core.discovery_runtime import _host


def test_discovery_runtime_host_parser_is_fail_closed():
    assert _host('https://chat.deepseek.com/path') == 'chat.deepseek.com'
    assert _host('not a url') == ''


def test_behavior_route_and_ai_route_are_exposed():
    src=open('control_panel.py',encoding='utf-8-sig').read()
    assert '/api/discovery/runs/<provider_id>/<run_id>/behavior' in src
    assert '/api/discovery/runs/<provider_id>/<run_id>/ai-assist' in src
    assert 'user_confirmation_required' in src
