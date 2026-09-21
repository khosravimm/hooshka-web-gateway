"""Consolidated gates ported from hwg-next-0.9.3 (no-hardcode/reuse-first).

Covers: fullwidth unicode normalization in parse_tool_calls, fail-closed
allowlist policy, tool adapter structured errors, commitment tracker,
focus guard defaults.
"""
import pytest

from core.commitment import Commitment, CommitmentError, CommitmentTracker
from core.focus_guard import FocusGuard, FocusViolation
from core.tool_adapter import ToolAdapterError, adapt_tool_call
from core.tool_allowlist import ToolProtocolError, filter_calls_by_allowlist
from core.tool_protocol import parse_tool_calls
from core.unicode_norm import normalize_unicode


def test_fullwidth_braces_parse_as_tool_call():
    content, calls = parse_tool_calls('｛"tool_calls": [｛"name": "bash"，"arguments": ｛｝｝]｝')
    assert calls, "fullwidth JSON envelope must be recognized"
    assert content is None or "bash" not in (content or "")


def test_normalize_unicode_maps_fullwidth():
    assert normalize_unicode("｛｝：，") == "{}:,"
    assert normalize_unicode("plain") == "plain"


def test_empty_allowlist_is_not_wildcard():
    calls = [{"name": "bash", "arguments": {}}]
    with pytest.raises(ToolProtocolError):
        filter_calls_by_allowlist(calls, set())


def test_unknown_tool_names_are_dropped_or_rejected():
    calls = [{"name": "bash", "arguments": {}}, {"name": "evil", "arguments": {}}]
    kept = filter_calls_by_allowlist(calls, {"bash"})
    assert [c["name"] for c in kept] == ["bash"]
    with pytest.raises(ToolProtocolError):
        filter_calls_by_allowlist(calls, {"other"})


def test_tool_adapter_rejects_unsupported_with_structured_error():
    with pytest.raises(ToolAdapterError) as ei:
        adapt_tool_call("nope", {}, [{"name": "bash"}])
    assert ei.value.to_dict()["error"]["code"] == "unsupported_tool"
    ok = adapt_tool_call("bash", {"command": "x"}, [{"name": "bash"}])
    assert ok == {"native_name": "bash", "arguments": {"command": "x"}}


def test_commitment_retry_only_before_send():
    t = CommitmentTracker("cid-1")
    assert t.may_retry()
    t.require_retry_safe()
    t.advance(Commitment.MAYBE_SENT)
    with pytest.raises(CommitmentError):
        t.require_retry_safe()
    with pytest.raises(CommitmentError):
        t.advance(Commitment.NOT_SENT)
    t.advance(Commitment.COMMITTED)
    t.advance(Commitment.TERMINAL)
    assert t.state == Commitment.TERMINAL


def test_focus_guard_default_denies_background():
    g = FocusGuard()
    assert not g.may_bring_to_front()
    with pytest.raises(FocusViolation):
        g.deny("poll")
    with g.user_initiated("open browser for login"):
        assert g.may_bring_to_front()
    assert not g.may_bring_to_front()
