from core.local_tools import LocalToolRegistry, local_tool_descriptors
from core.tool_contract import ToolAuthorizationMode, ToolRiskClass


def test_local_tools_have_canonical_read_only_contract(tmp_path):
    descriptors = local_tool_descriptors()
    assert len(descriptors) == 11
    assert {d.name for d in descriptors} == {
        'tool_catalog','list_drives','system_info','environment_info','list_processes',
        'network_listeners','list_files','file_info','find_files','read_file','search_files'
    }
    for item in descriptors:
        assert item.source == 'hwg_native'
        assert item.risk_class is ToolRiskClass.READ_ONLY
        assert item.authorization_mode is ToolAuthorizationMode.NONE
        assert item.annotations.read_only_hint is True
        assert item.annotations.destructive_hint is False
        assert item.annotations.idempotent_hint is True
        assert item.annotations.open_world_hint is False


def test_tool_catalog_uses_canonical_contract(tmp_path):
    catalog = LocalToolRegistry([tmp_path]).tool_catalog()['tools']
    assert len(catalog) == 11
    first = next(x for x in catalog if x['name'] == 'list_files')
    assert first['risk_class'] == 'READ_ONLY'
    assert first['authorization_mode'] == 'none'
    assert first['annotations']['readOnlyHint'] is True
