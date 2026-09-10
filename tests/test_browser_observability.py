from core.browser_observability import BrowserEvidenceMismatch, BrowserModelEvidence, normalize_model_marker


def test_normalize_model_marker_matches_display_and_id():
    assert normalize_model_marker("GLM-5.3") == normalize_model_marker("glm-5.3")
    assert normalize_model_marker("Qwen3.8-Max") == normalize_model_marker("qwen3.8-max")


def test_model_evidence_accepts_consistent_chain():
    ev = BrowserModelEvidence(
        provider="zai-web",
        requested_model="zai-web",
        expected_upstream_model="glm-5.3",
        ui_selected_model="GLM-5.3",
        backend_request_model="glm-5.3",
        response_model="glm-5.3",
    )
    result = ev.validate()
    assert result["verified"] is True
    assert result["backend_verified"] is True


def test_model_evidence_rejects_flash_mismatch():
    ev = BrowserModelEvidence(
        provider="zai-web",
        requested_model="zai-web",
        expected_upstream_model="glm-5.3",
        ui_selected_model="GLM-5.3-Flash",
        backend_request_model="x-preview-l",
    )
    try:
        ev.validate()
    except BrowserEvidenceMismatch as exc:
        assert "selected model" in str(exc)
    else:
        raise AssertionError("mismatch was not rejected")


def test_model_evidence_rejects_missing_backend_provenance():
    ev = BrowserModelEvidence(
        provider="qwen-web",
        requested_model="qwen-web",
        expected_upstream_model="qwen3.8-max",
        frontend_state_models=["qwen3.8-max"],
    )
    try:
        ev.validate()
    except BrowserEvidenceMismatch as exc:
        assert "backend request" in str(exc)
    else:
        raise AssertionError("missing backend evidence was not rejected")
