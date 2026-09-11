from core.providers import ChatCompletionRequest, ProviderCapabilities
from core.tool_compat import (
    drop_optional_tools_for_text_only_provider,
    request_requires_tools,
    tool_choice_requires_tool,
)
from tests.test_core import MockProvider


def _request(tool_choice=None):
    return ChatCompletionRequest(
        model="qwen-web",
        messages=[{"role": "user", "content": "hello"}],
        tools=[{"type": "function", "function": {"name": "read_file"}}],
        tool_choice=tool_choice,
    )


def test_auto_or_missing_tool_choice_is_optional():
    assert tool_choice_requires_tool(None) is False
    assert tool_choice_requires_tool("auto") is False
    assert tool_choice_requires_tool("none") is False
    assert request_requires_tools(_request()) is False
    assert request_requires_tools(_request("auto")) is False


def test_required_tool_choice_is_not_downgraded():
    req = _request({"type": "function", "function": {"name": "read_file"}})
    provider = MockProvider(provider_id="qwen-web")
    provider._capabilities.tools = False

    assert request_requires_tools(req) is True
    assert drop_optional_tools_for_text_only_provider(req, provider) is False
    assert req.tools is not None


def test_optional_tool_schema_is_dropped_for_text_only_provider():
    req = _request("auto")
    provider = MockProvider(provider_id="qwen-web")
    provider._capabilities.tools = False

    assert drop_optional_tools_for_text_only_provider(req, provider) is True
    assert req.tools is None
    assert req.tool_choice is None
    assert req.provider_options["optional_tools_dropped"]["provider_id"] == "qwen-web"


def test_tool_capable_provider_keeps_tools():
    req = _request("auto")
    provider = MockProvider(provider_id="chatgpt-web")
    provider._capabilities.tools = True

    assert drop_optional_tools_for_text_only_provider(req, provider) is False
    assert req.tools is not None
