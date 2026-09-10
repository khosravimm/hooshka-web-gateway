from core.upstream_response import classify_initial_response


def test_sse_200_is_stream():
    d = classify_initial_response(http_status=200, content_type="text/event-stream; charset=utf-8")
    assert d.kind == "stream"
    assert d.code == "sse"
    assert d.terminal is False


def test_deepseek_muted_inside_http_200_is_terminal_account_local():
    body = {"code": 0, "data": {"biz_code": 5, "biz_msg": "user is muted", "biz_data": {"is_muted": 1, "mute_until": 123}}}
    d = classify_initial_response(http_status=200, content_type="application/json", json_body=body)
    assert d.kind == "failure"
    assert d.code == "account_local_muted"
    assert d.terminal is True
    assert d.retryable is False
    assert d.details["account_state"] == "muted"
    assert "biz_msg" not in d.details


def test_http_200_application_error_is_not_sse_success():
    body = {"code": 0, "data": {"biz_code": 7, "biz_msg": "some upstream detail"}}
    d = classify_initial_response(http_status=200, content_type="application/json", json_body=body)
    assert d.code == "application_error"
    assert d.terminal is True


def test_rate_limit_is_retryable_but_terminal_for_attempt():
    d = classify_initial_response(http_status=429, content_type="application/json")
    assert d.code == "rate_limit"
    assert d.retryable is True
    assert d.terminal is True


def test_unexpected_200_content_type_fails_closed():
    d = classify_initial_response(http_status=200, content_type="text/html")
    assert d.code == "unexpected_content_type"
    assert d.terminal is True
