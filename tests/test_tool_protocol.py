import json

from core.tool_protocol import parse_tool_calls, serialize_messages, strong_auto_tool_signal


TOOLS = [{
    "type": "function",
    "function": {
        "name": "bash",
        "description": "Run a local shell command",
        "parameters": {
            "type": "object",
            "properties": {"command": {"type": "string"}},
            "required": ["command"],
        },
    },
}]


def test_serialize_preserves_system_user_assistant_and_tool_result():
    messages = [
        {"role": "system", "content": "Be exact."},
        {"role": "user", "content": "Check WSL"},
        {"role": "assistant", "content": None, "tool_calls": [{
            "id": "call_1",
            "type": "function",
            "function": {"name": "bash", "arguments": '{"command":"wsl --status"}'},
        }]},
        {"role": "tool", "tool_call_id": "call_1", "name": "bash", "content": "Default Version: 2"},
    ]
    text = serialize_messages(messages, tools=TOOLS, tool_choice="auto")
    assert "[SYSTEM TOOL INSTRUCTIONS]" in text
    assert "[SYSTEM]\nBe exact." in text
    assert '"name": "bash"' in text
    assert "[TOOL RESULT id=call_1 name=bash]" in text
    assert "Default Version: 2" in text


def test_parse_json_tool_call():
    content, calls = parse_tool_calls('{"tool_calls":[{"name":"bash","arguments":{"command":"wsl --status"}}]}')
    assert content is None
    assert calls[0]["function"]["name"] == "bash"
    assert json.loads(calls[0]["function"]["arguments"])["command"] == "wsl --status"


def test_parse_fullwidth_multi_dsml():
    text = r'''<｜｜DSML｜｜ calls>
<｜｜DSML｜｜ invoke name="bash"><｜｜DSML｜｜ parameter name="command" string="true">wsl --status\</｜｜DSML｜｜ parameter>\</｜｜DSML｜｜ invoke>
<｜｜DSML｜｜ invoke name="bash"><｜｜DSML｜｜ parameter name="command" string="true">Get-CimInstance Win32\_ComputerSystem\</｜｜DSML｜｜ parameter>\</｜｜DSML｜｜ invoke>
\</｜｜DSML｜｜ calls>'''
    content, calls = parse_tool_calls(text)
    assert content is None
    assert len(calls) == 2
    assert json.loads(calls[1]["function"]["arguments"])["command"] == "Get-CimInstance Win32_ComputerSystem"


def test_strong_auto_signal_explicit_user_tool_request():
    reason = strong_auto_tool_signal(
        '{"final":"AWA_REUSE_OK"}',
        TOOLS,
        latest_user_text="Use the bash tool to run Write-Output AWA_REUSE_OK",
    )
    assert reason == "explicit_user_tool_request:bash"


def test_strong_auto_signal_does_not_retry_ordinary_final():
    reason = strong_auto_tool_signal(
        "4",
        TOOLS,
        latest_user_text="What is 2+2?",
    )
    assert reason is None


def test_strong_auto_signal_detects_false_refusal():
    reason = strong_auto_tool_signal(
        "I can't access the workspace shell in this session.",
        TOOLS,
        latest_user_text="Check the project status.",
    )
    assert reason is not None