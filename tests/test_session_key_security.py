"""Verify-only key hashing + session/logout endpoint contracts."""
import sys
from pathlib import Path
from flask import Flask

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.governance import AuthManager
from core.key_hash import hash_token, is_hash, normalize_ref


def test_hash_format_and_stability():
    h = hash_token("abc")
    assert h.startswith("sha256:") and len(h) == 71
    assert hash_token("abc") == h
    assert hash_token("abd") != h
    assert is_hash(h) and not is_hash("abc")


def test_stored_form_contains_no_plaintext():
    auth = AuthManager()
    auth._enabled = True
    auth.add_key("super-secret-token", "u1")
    stored = list(auth._api_keys)
    assert stored == [hash_token("super-secret-token")]
    assert "super-secret-token" not in repr(auth._api_keys)


def test_verify_roundtrip_and_reject():
    auth = AuthManager()
    auth._enabled = True
    auth.add_key("tok-1", "u1", {"role": "x"})
    assert auth.verify("tok-1")["identity"] == "u1"
    assert auth.verify("tok-2") is None
    assert auth.verify("") is None


def test_load_keys_accepts_plaintext_and_hash_refs():
    auth = AuthManager()
    auth._enabled = True
    ref = hash_token("tok-h")
    auth.load_keys({"tok-plain": "u-plain", ref: {"identity": "u-hash"}})
    assert auth.verify("tok-plain")["identity"] == "u-plain"
    assert auth.verify("tok-h")["identity"] == "u-hash"


def test_panel_session_logout_endpoints_exist():
    text = (ROOT / "control_panel.py").read_text(encoding="utf-8")
    assert "@control_panel_bp.route('/api/providers/<provider_id>/session')" in text
    assert "def api_provider_session(provider_id):" in text
    assert "@control_panel_bp.route('/api/providers/<provider_id>/logout', methods=['POST'])" in text
    assert '"confirm": true' in text or "{'confirm': true}" in text or '"confirm"' in text
    assert "provider_logout" in text and "provider_session_checked" in text


def test_panel_key_creation_stores_hash_only():
    text = (ROOT / "control_panel.py").read_text(encoding="utf-8")
    assert "hash_token(token)" in text
    assert '"key_ref": ref' in text or "'key_ref': ref" in text or '"key_ref"' in text


def test_extract_key_accepts_bearer_header_only():
    app = Flask(__name__)
    auth = AuthManager()

    with app.test_request_context('/v1/models', headers={'Authorization': 'Bearer secret-token'}):
        assert auth.extract_key() == 'secret-token'

    with app.test_request_context('/v1/models?api_key=secret-token'):
        assert auth.extract_key() is None
