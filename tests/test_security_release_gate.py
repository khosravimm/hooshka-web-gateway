from flask import Flask, g

from core.governance import auth_manager, auth_middleware
from core.security_gate import is_loopback_host, validate_remote_exposure


def test_loopback_detection_is_strict():
    assert is_loopback_host('127.0.0.1')
    assert is_loopback_host('::1')
    assert is_loopback_host('localhost')
    assert not is_loopback_host('0.0.0.0')
    assert not is_loopback_host('192.168.1.10')
    assert not is_loopback_host('10.0.0.5')


def test_remote_health_does_not_bypass_auth():
    app = Flask(__name__)
    old = auth_manager._enabled
    auth_manager._enabled = True
    try:
        with app.test_request_context('/health', environ_base={'REMOTE_ADDR': '10.0.0.5'}):
            result = auth_middleware()
            assert result is not None
            assert result[1] == 401
    finally:
        auth_manager._enabled = old


def test_loopback_health_is_allowed_without_key():
    app = Flask(__name__)
    old = auth_manager._enabled
    auth_manager._enabled = True
    try:
        with app.test_request_context('/health', environ_base={'REMOTE_ADDR': '127.0.0.1'}):
            result = auth_middleware()
            assert result is None
            assert g.identity['identity'] == 'health-check'
    finally:
        auth_manager._enabled = old


def test_non_loopback_bind_fails_without_full_remote_policy():
    cfg = {
        'server': {'host': '0.0.0.0'},
        'governance': {'auth': {'enabled': True}, 'rate_limiting': {'enabled': True}, 'audit': {'enabled': True}},
    }
    errors = validate_remote_exposure(cfg)
    assert any('remote_access.enabled' in e for e in errors)
    assert any('TLS termination' in e for e in errors)
    assert any('network ACL' in e for e in errors)


def test_non_loopback_bind_allows_explicit_complete_policy():
    cfg = {
        'server': {'host': '192.168.1.20'},
        'governance': {
            'auth': {'enabled': True},
            'rate_limiting': {'enabled': True},
            'audit': {'enabled': True},
            'remote_access': {
                'enabled': True,
                'tls_termination': True,
                'network_acl': True,
            },
        },
    }
    assert validate_remote_exposure(cfg) == []


def test_loopback_bind_does_not_require_remote_policy():
    assert validate_remote_exposure({'server': {'host': '127.0.0.1'}}) == []


def test_audit_sanitizer_redacts_secret_and_content_fields():
    from core.governance import _sanitize_audit_value
    event = {
        'provider': 'deepseek-web',
        'Authorization': 'Bearer top-secret',
        'api_key': 'sk-test-secret',
        'cookie_value': 'session=secret',
        'messages': [{'role': 'user', 'content': 'sensitive prompt'}],
        'nested': {'prompt': 'private', 'safe': 'metadata'},
    }
    clean = _sanitize_audit_value(event)
    assert clean['provider'] == 'deepseek-web'
    assert clean['Authorization'] == '[REDACTED]'
    assert clean['api_key'] == '[REDACTED]'
    assert clean['cookie_value'] == '[REDACTED]'
    assert clean['messages'] == '[REDACTED]'
    assert clean['nested']['prompt'] == '[REDACTED]'
    assert clean['nested']['safe'] == 'metadata'


def test_hwg_request_body_limit_is_enforced():
    from main import create_app
    app = create_app('config.yaml')
    app.config['TESTING'] = True
    app.config['MAX_CONTENT_LENGTH'] = 64
    client = app.test_client()
    payload = '{"id":"' + ('x' * 256) + '"}'
    resp = client.post('/panel/api/providers', data=payload, content_type='application/json')
    assert resp.status_code == 413


def test_default_hwg_body_limit_is_bounded():
    from main import create_app
    app = create_app('config.yaml')
    assert app.config['MAX_CONTENT_LENGTH'] == 8 * 1024 * 1024
