import json

from core.tool_protocol import parse_tool_calls, parse_tool_envelope, serialize_messages, strong_auto_tool_signal


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


def test_tool_instruction_requires_single_fenced_json_envelope():
    text = serialize_messages([{"role": "user", "content": "write files"}], tools=TOOLS, tool_choice="auto")
    assert "one fenced `json` code block" in text
    assert "AT MOST ONE tool call" in text
    assert "```json" in text


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

def test_parse_compact_key_value_arguments_normalizes_to_json():
    text='{"tool_calls":[{"name":"hwg_tool_capability_probe","arguments":"marker=HWG_TOOL_PROBE_123456"}]}'
    content,calls,valid=parse_tool_envelope(text)
    assert valid is True
    assert calls and calls[0]['function']['name']=='hwg_tool_capability_probe'
    assert json.loads(calls[0]['function']['arguments'])=={'marker':'HWG_TOOL_PROBE_123456'}


def test_parse_tool_envelope_repairs_dom_deescaped_json_string_arguments():
    text = (
        '{"tool_calls":[{"type":"function","function":{'
        '"name":"hwg_tool_capability_probe",'
        '"arguments":"{"marker":"HWG_TOOL_PROBE_395404"}"}}]}'
    )

    content, calls, valid = parse_tool_envelope(text)

    assert valid is True
    assert content is None
    assert calls and calls[0]["function"]["name"] == "hwg_tool_capability_probe"
    assert json.loads(calls[0]["function"]["arguments"]) == {
        "marker": "HWG_TOOL_PROBE_395404"
    }


def test_parse_tool_envelope_repairs_deescaped_powershell_command_with_windows_path_and_quotes():
    raw = (
        '{"tool_calls": [{"name": "bash", "arguments": {'
        '"command": "New-Item -ItemType Directory -Path "src\\taskflow", "tests" -Force | Select-Object FullName", '
        '"description": "Create package and tests directories"}, "id": "call_1cbfc894"}]}'
    )
    content, calls, valid = parse_tool_envelope(raw)
    assert valid is True
    assert content is None
    assert calls and calls[0]["function"]["name"] == "bash"
    args = json.loads(calls[0]["function"]["arguments"])
    assert args["command"] == 'New-Item -ItemType Directory -Path "src\\taskflow", "tests" -Force | Select-Object FullName'
    assert args["description"] == "Create package and tests directories"


def test_parse_tool_envelope_repairs_unescaped_shell_argument_quotes_around_comma():
    raw = (
        '{"tool_calls": [{"name": "bash", "arguments": {'
        '"command": "New-Item -ItemType Directory -Path "src\\taskflow", "tests" -Force | Select-Object FullName", '
        '"description": "Create package and tests directories"}, "id": "call_live"}]}'
    )
    content, calls, valid = parse_tool_envelope(raw)
    assert valid is True
    assert content is None
    args = json.loads(calls[0]["function"]["arguments"])
    assert args["command"] == 'New-Item -ItemType Directory -Path "src\\taskflow", "tests" -Force | Select-Object FullName'
    assert args["description"] == "Create package and tests directories"


def test_parse_tool_envelope_repairs_missing_terminal_closers_from_live_todowrite():
    raw = (
        '{"tool_calls": [{"name": "todowrite", "arguments": {"todos": ['
        '{"content": "Create package", "status": "in_progress", "priority": "high"}, '
        '{"content": "Run tests", "status": "pending", "priority": "high"}]}}'
    )
    content, calls, valid = parse_tool_envelope(raw)
    assert valid is True
    assert content is None
    assert calls[0]["function"]["name"] == "todowrite"
    args = json.loads(calls[0]["function"]["arguments"])
    assert args["todos"][1]["content"] == "Run tests"


def test_truncated_json_repair_does_not_invent_unclosed_string_content():
    raw = '{"tool_calls":[{"name":"bash","arguments":{"command":"echo unfinished'
    content, calls, valid = parse_tool_envelope(raw)
    assert valid is False
    assert calls is None
    assert content == raw


def test_tool_instruction_requires_single_call_and_json_escaping():
    from core.tool_protocol import build_tool_instruction
    text = build_tool_instruction([{"type": "function", "function": {"name": "write", "description": "write", "parameters": {"type": "object"}}}])
    assert "AT MOST ONE tool call" in text
    assert "Every string argument MUST be valid JSON" in text
    assert "never batch multiple calls" in text
    assert "exactly one item in `tool_calls`" in text


def test_parse_tool_envelope_repairs_json_control_escape_in_windows_path():
    raw = r'{"tool_calls":[{"name":"write","arguments":{"filePath":"D:\Code\Repo\src\taskflow\init.py","content":"x"}}]}'
    content, calls, valid = parse_tool_envelope(raw)
    assert valid is True
    assert content is None
    args = json.loads(calls[0]["function"]["arguments"])
    assert args["filePath"] == r"D:\Code\Repo\src\taskflow\init.py"
    assert "\t" not in args["filePath"]


def test_serialize_assistant_tool_history_is_fenced_json():
    messages = [{
        "role": "assistant",
        "content": None,
        "tool_calls": [{
            "id": "call_1",
            "function": {
                "name": "write",
                "arguments": '{"filePath":"src/taskflow/__init__.py","content":"from __future__ import annotations"}',
            },
        }],
    }]
    text = serialize_messages(messages, tools=TOOLS, tool_choice="auto")
    assert '[ASSISTANT]\n```json\n{"tool_calls"' in text
    assert "src/taskflow/__init__.py" in text
    assert "from __future__ import annotations" in text
    assert text.rstrip().endswith("```")


def test_parse_tool_envelope_repairs_missing_object_closer_before_tool_calls_array_close():
    raw = (
        '{"tool_calls":[{"name":"write","arguments":{'
        '"filePath":"src/taskflow/service.py",'
        '"content":"from __future__ import annotations",'
        '"id":"call_live"}]}'
    )
    content, calls, valid = parse_tool_envelope(raw)
    assert valid is True
    assert content is None
    assert calls[0]["function"]["name"] == "write"
    args = json.loads(calls[0]["function"]["arguments"])
    assert args["filePath"] == "src/taskflow/service.py"
    assert args["content"] == "from __future__ import annotations"


def test_missing_container_repair_rejects_extra_unmatched_closer():
    raw = '{"tool_calls":[{"name":"write","arguments":{}}]]}'
    content, calls, valid = parse_tool_envelope(raw)
    assert valid is False
    assert calls is None


def test_parse_tool_envelope_accepts_renderer_chrome_before_repairable_tool_json():
    raw = (
        'json\nCopy\nDownload\n'
        '{"tool_calls":[{"name":"write","arguments":{'
        '"filePath":"pyproject.toml","content":"[project]\\nname = \\\"taskflow\\\"",'
        '"id":"call_live"}]}'
    )
    content, calls, valid = parse_tool_envelope(raw)
    assert valid is True
    assert content is None
    assert calls[0]["function"]["name"] == "write"
    args = json.loads(calls[0]["function"]["arguments"])
    assert args["filePath"] == "pyproject.toml"
    assert 'name = "taskflow"' in args["content"]


def test_renderer_chrome_fallback_does_not_accept_arbitrary_prose_prefix():
    raw = 'Here is your tool call:\n{"tool_calls":[{"name":"write","arguments":{"filePath":"x","content":"y"}]}'
    content, calls, valid = parse_tool_envelope(raw)
    assert valid is False
    assert calls is None
