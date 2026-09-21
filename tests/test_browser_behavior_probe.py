from core.browser_behavior_probe import ProbePolicy, click_guard


def test_click_is_denied_without_explicit_approval():
    allowed, reason = click_guard({"text":"DeepThink","type":""}, ProbePolicy())
    assert allowed is False
    assert reason == "click_not_approved"


def test_reversible_toggle_click_can_be_approved():
    allowed, reason = click_guard({"text":"DeepThink","type":"button"}, ProbePolicy(allow_click=True))
    assert allowed is True
    assert reason == "approved_reversible_click"


def test_send_submit_and_destructive_clicks_fail_closed():
    policy = ProbePolicy(allow_click=True)
    assert click_guard({"text":"Send message"}, policy)[0] is False
    assert click_guard({"text":"Okay", "type":"submit"}, policy)[0] is False
    assert click_guard({"text":"Reset", "destructive":True}, policy)[0] is False
