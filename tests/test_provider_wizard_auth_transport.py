from core.provider_wizard_stage_runtime import classify_auth_transport_failure


def test_failed_signin_transport_is_detected_without_visible_toast():
    out = classify_auth_transport_failure({
        "visible_text": "",
        "resources": [
            {
                "name": "https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key=public",
                "age_ms": 120000,
                "response_status": None,
                "transfer_size": 0,
            }
        ],
    })
    assert out is not None
    assert out["kind"] == "AUTH_PROVIDER_BROKEN"
    assert out["reason"] == "auth_provider_transport_failure"
    assert out["user_action_required"] is False
    assert out["evidence"][0]["name"].endswith("accounts:signInWithPassword")


def test_identity_project_bootstrap_failure_is_detected_without_visible_toast():
    out = classify_auth_transport_failure({
        "visible_text": "",
        "resources": [
            {
                "name": "https://identitytoolkit.googleapis.com/v1/projects?key=public",
                "age_ms": 1000,
                "response_status": None,
                "transfer_size": 0,
            }
        ],
    })
    assert out is not None
    assert out["kind"] == "AUTH_PROVIDER_BROKEN"
    assert out["user_action_required"] is False


def test_firebase_webconfig_bootstrap_failure_is_detected():
    out = classify_auth_transport_failure({
        "visible_text": "",
        "resources": [
            {
                "name": "https://firebase.googleapis.com/v1alpha/projects/-/apps/1:123:web:abc/webConfig",
                "age_ms": 500,
                "response_status": None,
                "transfer_size": 0,
            }
        ],
    })
    assert out is not None
    assert out["kind"] == "AUTH_PROVIDER_BROKEN"


def test_visible_network_error_plus_recent_identity_failure_is_detected():
    out = classify_auth_transport_failure({
        "visible_text": "Network request failed. Please check your internet connection and try again.",
        "resources": [
            {
                "name": "https://identitytoolkit.googleapis.com/v1/projects?key=public",
                "age_ms": 1000,
                "response_status": None,
                "transfer_size": 0,
            }
        ],
    })
    assert out is not None
    assert out["kind"] == "AUTH_PROVIDER_BROKEN"


def test_old_auth_failure_is_ignored():
    out = classify_auth_transport_failure({
        "visible_text": "Network request failed.",
        "resources": [
            {
                "name": "https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key=public",
                "age_ms": 901000,
                "response_status": None,
                "transfer_size": 0,
            }
        ],
    })
    assert out is None
