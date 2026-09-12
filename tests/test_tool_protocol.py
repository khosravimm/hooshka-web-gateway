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

def test_parse_tool_calls_tolerates_raw_windows_backslashes():
    text = '{"tool_calls":[{"name":"read","arguments":{"filePath":"D:\\Code\\hooshka-web-gateway\\README.md"}}]}'
    # Simulate the DOM text DeepSeek produced for Kilo: JSON-visible Windows
    # backslashes that are not valid JSON escapes.
    text = text.replace('\\\\', '\\')
    content, calls = parse_tool_calls(text)
    assert content is None
    assert calls[0]["function"]["name"] == "read"
    assert "D:\\\\Code\\\\hooshka-web-gateway\\\\README.md" in calls[0]["function"]["arguments"]


def test_parse_tool_calls_repairs_unescaped_quotes_inside_command_argument():
    text = (
        "I'll check the WSL status and locate the project there.\n\n"
        '{"tool_calls":['
        '{"name":"bash","arguments":{"command":"wsl --list --verbose"}},'
        '{"name":"bash","arguments":{"command":"wsl -e bash -lc "find /home /mnt /root /opt -maxdepth 4 -iname \'opennotebook\' -o -maxdepth 4 -iname \'Open NoteBook*\' 2>/dev/null""}}'
        ']}'
    )
    content, calls = parse_tool_calls(text)

    assert content == "I'll check the WSL status and locate the project there."
    assert [call["function"]["name"] for call in calls] == ["bash", "bash"]
    assert json.loads(calls[0]["function"]["arguments"])["command"] == "wsl --list --verbose"
    assert json.loads(calls[1]["function"]["arguments"])["command"] == (
        'wsl -e bash -lc "find /home /mnt /root /opt -maxdepth 4 -iname \'opennotebook\' '
        '-o -maxdepth 4 -iname \'Open NoteBook*\' 2>/dev/null"'
    )


def test_parse_tool_calls_uses_first_balanced_json_object():
    text = '{"tool_calls":[{"name":"edit","arguments":{"filePath":".runtime/x.txt","oldString":"A","newString":"B"}}]}\n\n[TOOL RESULT id=call_1]\nok\n\n{"tool_calls":[{"name":"bash","arguments":{"command":"Get-Content .runtime/x.txt"}}]}'
    content, calls = parse_tool_calls(text)

    assert calls is not None
    assert calls[0]["function"]["name"] == "edit"
    assert '"newString": "B"' in calls[0]["function"]["arguments"]


def test_parse_tool_calls_normalizes_kilo_argument_aliases():
    text = '{"tool_calls":[{"name":"edit","arguments":{"file_path":".runtime/x.txt","old_string":"A","new_string":"B"}}]}'
    _, calls = parse_tool_calls(text)

    assert calls[0]["function"]["name"] == "edit"
    assert '"filePath": ".runtime/x.txt"' in calls[0]["function"]["arguments"]
    assert '"oldString": "A"' in calls[0]["function"]["arguments"]
    assert '"newString": "B"' in calls[0]["function"]["arguments"]


def test_parse_tool_calls_preserves_tool_name_and_normalizes_path_alias():
    text = '{"tool_calls":[{"name":"read_file","arguments":{"path":"README.md"}}]}'
    _, calls = parse_tool_calls(text)

    assert calls[0]["function"]["name"] == "read_file"
    assert '"filePath": "README.md"' in calls[0]["function"]["arguments"]



def test_parse_xmlish_tool_call_json_wrapper_from_web_chat():
    text = '<tool_call>{"name":"edit","arguments":{"filePath":".runtime/x.txt","oldString":"A","newString":"B"}}</tool_call>'
    content, calls = parse_tool_calls(text)

    assert content is None
    assert calls[0]["function"]["name"] == "edit"
    args = json.loads(calls[0]["function"]["arguments"])
    assert args["filePath"] == ".runtime/x.txt"
    assert args["oldString"] == "A"
    assert args["newString"] == "B"


def test_parse_xmlish_tool_call_arg_key_value_from_web_chat():
    text = """I'll read it first.
<tool_call>read<arg_key>filePath</arg_key><arg_value>D:\\Code\\hooshka-web-gateway\\.runtime\\kilogate_qwen_patch_probe.txt</arg_value></tool_call>
[NO TOOL]
I should not invent the tool result."""
    content, calls = parse_tool_calls(text)

    assert calls[0]["function"]["name"] == "read"
    args = json.loads(calls[0]["function"]["arguments"])
    assert args["filePath"] == "D:\\Code\\hooshka-web-gateway\\.runtime\\kilogate_qwen_patch_probe.txt"
    assert "I should not invent" in content
