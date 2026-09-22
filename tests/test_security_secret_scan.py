from scripts.security_secret_scan import scan_text


def test_secret_scan_flags_plaintext_credentials():
    text = '''
Authorization: Bearer abcdefghijklmnop
api_key: sk-abcdefghijklmnop
password: hunter2
'''
    kinds = {x['kind'] for x in scan_text(text)}
    assert 'bearer_token' in kinds
    assert 'openai_style_key' in kinds
    assert 'sensitive_value' in kinds


def test_secret_scan_allows_hashes_empty_and_redacted_values():
    text = '''
api_keys: {}
api_key: sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
Authorization: [REDACTED]
cookie: null
'''
    assert scan_text(text) == []
