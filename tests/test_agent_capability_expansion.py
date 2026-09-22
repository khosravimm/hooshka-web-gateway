from core.local_tools import LocalToolRegistry, LocalToolError, agent_tool_definitions

def test_catalog_exposes_nine_read_only_capabilities(tmp_path):
    reg=LocalToolRegistry([tmp_path]); cat=reg.tool_catalog()
    assert len(cat['tools']) == 11
    assert all(x['risk']=='read_only' for x in cat['tools'])

def test_find_and_file_info(tmp_path):
    (tmp_path/'sub').mkdir(); (tmp_path/'sub'/'note.txt').write_text('hello',encoding='utf-8')
    reg=LocalToolRegistry([tmp_path]); found=reg.find_files(str(tmp_path),'*.txt')
    assert found['items'][0]['name']=='note.txt'
    assert reg.file_info(str(tmp_path/'sub'/'note.txt'))['size']==5

def test_system_and_environment_are_bounded(tmp_path):
    reg=LocalToolRegistry([tmp_path]); assert reg.system_info()['hostname']
    env=reg.environment_info(['USERNAME','SECRET_TOKEN'])['environment']
    assert 'SECRET_TOKEN' not in env

def test_unknown_or_mutating_tool_fails_closed(tmp_path):
    reg=LocalToolRegistry([tmp_path])
    for name in ('write_file','run_command','delete_file','mcp_call'):
        try: reg.execute(name,{})
        except LocalToolError: pass
        else: raise AssertionError(name+' must fail closed')
