
from core.provider_risk import detect_provider_risk


def test_detects_daily_usage_limit_wait_window():
    signal = detect_provider_risk("You have reached the daily usage limit. Please wait 18 hours before trying again.")

    assert signal is not None
    assert signal.kind == "quota_limit"
    assert signal.failure_class == "quota_limit_observed"
    assert signal.wait_hours == 18


def test_detects_high_demand_as_quota_not_model_failure():
    signal = detect_provider_risk("The service is currently experiencing high demand. Please try again later.")

    assert signal is not None
    assert signal.kind == "quota_limit"
    assert signal.failure_class == "quota_limit_observed"


def test_detects_slider_challenge_separately():
    signal = detect_provider_risk("Please drag the slider below to complete the verification.")

    assert signal is not None
    assert signal.kind == "challenge"
    assert signal.failure_class == "risk_control_challenge_visible"


def test_ordinary_tool_text_is_not_risk():
    assert detect_provider_risk('{"tool_calls":[{"name":"read_file","arguments":{"path":"README.md"}}]}') is None
