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


import pytest


@pytest.mark.asyncio
async def test_behavior_probe_blocks_before_target_interaction(monkeypatch):
    from core.browser_behavior_probe import BehaviorAction, run_behavior_probe
    import core.visual_discovery as visual
    import core.browser_behavior_probe as behavior

    async def blocked_gate(_page, _action):
        return {"allowed":False,"classification":{"state":"login_required"}}

    async def snapshot_must_not_run(_page, _selector):
        raise AssertionError("snapshot must not run after blocked visual preflight")

    monkeypatch.setattr(visual, "visual_action_gate", blocked_gate)
    monkeypatch.setattr(behavior, "_snapshot", snapshot_must_not_run)
    with pytest.raises(PermissionError, match="visual_preflight_blocked:login_required"):
        await run_behavior_probe(object(), BehaviorAction("hover", "#x", "test"), ProbePolicy())