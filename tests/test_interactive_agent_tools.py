from pathlib import Path
from core.local_tools import LocalToolRegistry, LocalToolError, agent_tool_definitions


def test_list_files_returns_directories_and_files(tmp_path):
    (tmp_path/'folder').mkdir(); (tmp_path/'a.txt').write_text('hello',encoding='utf-8')
    result=LocalToolRegistry([tmp_path]).list_files(str(tmp_path))
    assert {x['name'] for x in result['items']} == {'folder','a.txt'}
    assert next(x for x in result['items'] if x['name']=='folder')['type']=='directory'


def test_local_tools_fail_closed_outside_roots(tmp_path):
    reg=LocalToolRegistry([tmp_path])
    try: reg.list_files(str(tmp_path.parent))
    except LocalToolError: pass
    else: raise AssertionError('outside root must be rejected')


def test_interactive_chat_enables_agent_tool_loop():
    main=Path('main.py').read_text(encoding='utf-8-sig')
    js=Path('control_panel_ui/chat.js').read_text(encoding='utf-8-sig')
    assert 'agent_tool_definitions()' in main
    assert '_agent_tool_result_messages' in main
    assert 'for _step in range(4)' in main
    assert 'agent_mode: true' in js
    names={x['function']['name'] for x in agent_tool_definitions()}
    assert names == {'list_files','read_file','search_files'}


def test_tool_protocol_repairs_model_windows_drive_root():
    from core.tool_protocol import parse_tool_envelope
    raw = r'{"tool_calls":[{"name":"list_files","arguments":{"path":"D:\"}}]}'
    _content,calls,valid=parse_tool_envelope(raw)
    assert valid is True
    import json
    assert json.loads(calls[0]['function']['arguments'])['path'] == 'D:/'
