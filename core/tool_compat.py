from __future__ import annotations

from typing import Any

from core.providers import ChatCompletionRequest, Provider


def tool_choice_requires_tool(tool_choice: Any) -> bool:
    """Return true only when the client explicitly requires tool use.

    OpenAI-compatible clients often include a tools array for agent-capable
    models even when tool use is optional. Text-only Web providers may safely
    ignore that optional schema, but must fail closed when the client requires
    a tool call.
    """
    if tool_choice is None:
        return False
    if isinstance(tool_choice, str):
        return tool_choice not in {"auto", "none"}
    if isinstance(tool_choice, dict):
        choice_type = str(tool_choice.get("type", "")).lower()
        if choice_type in {"function", "tool", "required"}:
            return True
        if "function" in tool_choice or "tool" in tool_choice:
            return True
    return False


def request_requires_tools(request: ChatCompletionRequest) -> bool:
    return bool(request.tools) and tool_choice_requires_tool(request.tool_choice)


def drop_optional_tools_for_text_only_provider(
    request: ChatCompletionRequest,
    provider: Provider,
) -> bool:
    """Drop optional tool schemas for text-only providers.

    Returns True when a request was downgraded to text-only. The provider is not
    advertised as tool-capable and required tool calls are never downgraded.
    """
    if not request.tools:
        return False
    if provider.capabilities.tools:
        return False
    if tool_choice_requires_tool(request.tool_choice):
        return False

    request.tools = None
    request.tool_choice = None
    if request.provider_options is None:
        request.provider_options = {}
    request.provider_options["optional_tools_dropped"] = {
        "provider_id": provider.provider_id,
        "reason": "provider_is_text_only",
    }
    return True
