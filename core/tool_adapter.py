"""Tool Adapter: standard agent tool-calls -> provider native tools.

Ported from hwg-next-0.9.3 (hwg/tools/adapter.py). Fabricating tool success
is forbidden: unsupported tools raise a structured error instead of prose.
"""

from __future__ import annotations


class ToolAdapterError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message

    def to_dict(self) -> dict:
        return {"error": {"type": "tool_adapter_error", "code": self.code, "message": self.message}}


def adapt_tool_call(standard_name: str, arguments: dict, native_tools: list[dict]) -> dict:
    """Map a standard (OpenAI-style) function name to a native provider tool.

    Returns {"native_name": ..., "arguments": ...} or raises ToolAdapterError.
    """
    names = {t.get("name") for t in native_tools or []}
    if standard_name in names:
        return {"native_name": standard_name, "arguments": arguments}
    raise ToolAdapterError(
        "unsupported_tool",
        f"ابزار «{standard_name}» در این ارائه‌دهنده پشتیبانی نمی‌شود.",
    )
