from pathlib import Path

from core.account_session import normalize_session

ROOT = Path(__file__).resolve().parents[1]


def test_authenticated_session_normalizes():
    s = normalize_session({"authenticated": True, "composer_ready": True})
    assert s["access_state"] == "AUTHENTICATED"
    assert s["state"] == "authenticated"
    assert s["authenticated"] is True


def test_previous_authenticated_session_becomes_expired():
    s = normalize_session({"authenticated": False}, previous_access_state="AUTHENTICATED")
    assert s["access_state"] == "EXPIRED"
    assert s["state"] == "expired"


def test_explicit_access_states_remain_distinct():
    login = normalize_session({"authenticated": False}, "LOGIN_REQUIRED")
    interaction = normalize_session({"authenticated": False}, "USER_INTERACTION_REQUIRED")
    blocked = normalize_session({"authenticated": False}, "BLOCKED")
    assert login["access_state"] == "LOGIN_REQUIRED"
    assert interaction["access_state"] == "USER_INTERACTION_REQUIRED"
    assert blocked["access_state"] == "BLOCKED"


def test_shared_browser_logout_is_origin_scoped():
    text = (ROOT / "control_panel.py").read_text(encoding="utf-8-sig")
    start = text.index("async def _logout_origin")
    end = text.index("@control_panel_bp.route('/api/auth/keys')")
    block = text[start:end]
    assert "Storage.clearDataForOrigin" in block
    assert '"storageTypes": "all"' in block
    assert ".clear_cookies(" not in block


def test_account_centric_routes_and_structural_first_gate_exist():
    text = (ROOT / "control_panel.py").read_text(encoding="utf-8-sig")
    assert "/api/accounts/<path:account_id>/session" in text
    assert "/api/accounts/<path:account_id>/login/open" in text
    assert "/api/accounts/<path:account_id>/reauth" in text
    assert "/api/accounts/<path:account_id>/logout" in text
    start = text.index("def api_provider_session")
    end = text.index("def api_provider_logout", start)
    block = text[start:end]
    assert block.index("discovery_probe_auth_cdp") < block.index("_provider_session_checker")


def test_session_store_drops_secret_like_fields(tmp_path):
    import json
    from core.profile_store import update_account_session
    accounts = tmp_path / "account_instances"
    accounts.mkdir(parents=True)
    path = accounts / "p__default-account.json"
    path.write_text(json.dumps({"account_id":"p:default-account","session":{"state":"unknown"}}), encoding="utf-8")
    update_account_session("p:default-account", {
        "contract_version":"1.0.0", "access_state":"AUTHENTICATED", "state":"authenticated",
        "authenticated":True, "validated_at":"2026-01-01T00:00:00Z",
        "token":"SECRET", "cookie":"SID=SECRET", "api_key":"SECRET",
        "evidence":{"provider_authenticated":True,"composer_ready":True,"raw_cookie":"SECRET"},
    }, root=tmp_path)
    stored=json.loads(path.read_text(encoding="utf-8"))["session"]
    assert "token" not in stored and "cookie" not in stored and "api_key" not in stored
    assert "raw_cookie" not in stored["evidence"]
