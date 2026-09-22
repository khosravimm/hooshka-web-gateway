import json
import pytest

from core.provider_tool_probe import PROBE_TOOL_NAME, probe_provider_tool_call
from core.providers import ChatCompletionResponse, Choice, Message, Usage


class FakeProvider:
    provider_id = "fake-web"

    async def chat_completion(self, request):
        marker = request.messages[0]["content"].split("marker=", 1)[1].split(".", 1)[0]
        self.request = request
        return ChatCompletionResponse(
            id="probe", created=1, model=request.model,
            choices=[Choice(index=0, finish_reason="tool_calls", message=Message(
                role="assistant", content=None,
                tool_calls=[{"id":"call_probe","function":{
                    "name":PROBE_TOOL_NAME,
                    "arguments":json.dumps({"marker":marker}),
                }}],
            ))], usage=Usage(),
        )


@pytest.mark.asyncio
async def test_tool_probe_proves_forced_call_without_execution():
    provider = FakeProvider()
    result = await probe_provider_tool_call(provider, "fake-model")
    assert result["tested"] is True
    assert result["supported"] is True
    assert result["protocol_valid"] is True
    assert result["marker_match"] is True
    assert result["execution"] == "not_executed"
    assert provider.request.tool_choice["function"]["name"] == PROBE_TOOL_NAME


def test_provider_profile_persists_tool_qualification(tmp_path):
    from core.profile_store import update_provider_tool_capabilities
    profiles = tmp_path / "provider_profiles"
    profiles.mkdir(parents=True)
    profile = profiles / "fake-web__default.json"
    profile.write_text(json.dumps({
        "profile_id":"fake-web:default", "provider_id":"fake-web",
        "change_log":[], "artifact_version":"1.0.0",
    }), encoding="utf-8")
    result = {
        "schema_version":"1.0.0", "tested_at":"2026-09-22T00:00:00Z",
        "provider_id":"fake-web", "model":"fake-model", "tested":True,
        "supported":True, "evidence_level":"E2", "execution":"not_executed",
        "marker_match":True, "protocol_valid":True, "reason":"forced_tool_call_valid",
        "secret":"must-not-persist",
    }
    saved = update_provider_tool_capabilities("fake-web", result, tmp_path)
    latest = saved["tool_capabilities"]["latest"]
    assert latest["supported"] is True
    assert latest["execution"] == "not_executed"
    assert "secret" not in latest
    assert saved["change_log"][-1]["change"] == "provider_tool_capability_qualified"


class FakeNoToolProvider:
    provider_id = "plain-web"

    async def chat_completion(self, request):
        return ChatCompletionResponse(
            id="plain", created=1, model=request.model,
            choices=[Choice(index=0, finish_reason="stop", message=Message(
                role="assistant", content="plain text", tool_calls=None,
            ))], usage=Usage(),
        )


@pytest.mark.asyncio
async def test_tool_probe_does_not_infer_support_without_tool_call():
    result = await probe_provider_tool_call(FakeNoToolProvider(), "plain-model")
    assert result["tested"] is True
    assert result["supported"] is False
    assert result["reason"] == "no_tool_call_returned"


def test_discovery_explore_integrates_tool_probe_and_profile_persistence():
    src = open("control_panel.py", encoding="utf-8-sig").read()
    assert "probe_provider_tool_call(provider, model)" in src
    assert "update_provider_tool_capabilities(provider_id, tool_probe)" in src
    assert 'findings["tool_capability_probe"]' in src
