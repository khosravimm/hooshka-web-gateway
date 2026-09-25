import json
from pathlib import Path

import yaml

from core.profile_store import (
    migrate_legacy_inventory,
    load_persistent_inventory,
    provision_account_instance,
    account_runtime,
    deprovision_account_instance,
    update_connection_profile_name,
)


def _config(path: Path):
    path.write_text(yaml.safe_dump({
        "providers": [{
            "id": "deepseek-web", "type": "deepseek_web", "enabled": True,
            "runtime": {"kind": "chrome_cdp", "cdp_url": "http://127.0.0.1:9330",
                        "profile_dir": ".runtime-dev/shared-profile",
                        "home_url": "https://chat.deepseek.com/"},
            "config": {"transport_mode": "browser_ui"},
        }],
        "runtime_orchestration": {"shared_browser": {"enabled": True,
            "cdp_url": "http://127.0.0.1:9330", "profile_dir": ".runtime-dev/shared-profile"}},
    }, sort_keys=False), encoding="utf-8")


def test_second_same_origin_account_gets_dedicated_profile_and_port(tmp_path):
    cfg=tmp_path/'config.yaml'; root=tmp_path/'store'
    _config(cfg); migrate_legacy_inventory(cfg, root)
    account=provision_account_instance('deepseek-web','deepseek-web:office',cfg,root)
    assert account['browser_profile']['origin']=='https://chat.deepseek.com'
    assert account['browser_profile']['sharing_mode']=='exclusive_profile'
    assert account['browser_profile']['path'] != '.runtime-dev/shared-profile'
    assert account['runtime']['port'] != 9330
    assert account['runtime']['cdp_url'].startswith('http://127.0.0.1:')
    inv=load_persistent_inventory(root)
    assert inv['conflicts']==[]


def test_account_runtime_resolves_absolute_profile(tmp_path):
    cfg=tmp_path/'config.yaml'; root=tmp_path/'store'; project=tmp_path/'project'
    project.mkdir(); _config(cfg); migrate_legacy_inventory(cfg, root)
    provision_account_instance('deepseek-web','deepseek-web:office',cfg,root,preferred_port=9377)
    rt=account_runtime('deepseek-web:office',root,project)
    assert rt['port']==9377
    assert Path(rt['profile']).is_absolute()
    assert rt['profile'].endswith('deepseek-web__office')


def test_duplicate_account_or_port_is_rejected(tmp_path):
    cfg=tmp_path/'config.yaml'; root=tmp_path/'store'
    _config(cfg); migrate_legacy_inventory(cfg, root)
    provision_account_instance('deepseek-web','deepseek-web:a',cfg,root,preferred_port=9377)
    try:
        provision_account_instance('deepseek-web','deepseek-web:a',cfg,root)
        assert False, 'duplicate account must fail'
    except FileExistsError:
        pass
    try:
        provision_account_instance('deepseek-web','deepseek-web:b',cfg,root,preferred_port=9377)
        assert False, 'duplicate port must fail'
    except ValueError:
        pass


def test_deprovision_only_allows_dedicated_account_runtime(tmp_path):
    cfg=tmp_path/'config.yaml'; root=tmp_path/'store'
    _config(cfg); migrate_legacy_inventory(cfg, root)
    provision_account_instance('deepseek-web','deepseek-web:office',cfg,root)
    result=deprovision_account_instance('deepseek-web:office',root)
    assert result['deleted'] is True
    assert all(a['account_id']!='deepseek-web:office' for a in load_persistent_inventory(root)['account_instances'])
    try:
        deprovision_account_instance('deepseek-web:default-account',root)
        assert False, 'default migrated account must not be deprovisioned'
    except RuntimeError:
        pass


def test_control_plane_and_desktop_agent_have_account_runtime_routes():
    root=Path(__file__).resolve().parents[1]
    panel=(root/'control_panel.py').read_text(encoding='utf-8-sig')
    agent=(root/'desktop_runtime_agent.py').read_text(encoding='utf-8-sig')
    pool=(root/'core/browser_pool.py').read_text(encoding='utf-8-sig')
    assert "@control_panel_bp.route('/api/accounts', methods=['POST'])" in panel
    assert "/api/accounts/<path:account_id>/runtime/<action>" in panel
    assert "account_runtimes()" in agent and 'scope == "accounts"' in agent
    assert 'A tab is NOT a storage' in pool


def test_account_deprovision_route_is_guarded_and_profile_scoped():
    root=Path(__file__).resolve().parents[1]
    panel=(root/'control_panel.py').read_text(encoding='utf-8-sig')
    assert "@control_panel_bp.route('/api/accounts/<path:account_id>', methods=['DELETE'])" in panel
    assert 'Account deprovision requires confirm=true' in panel
    assert 'default_account_protected' in panel
    assert 'accounts_root = (_profile_root() / "accounts").resolve()' in panel


def test_connection_profile_name_is_suggested_and_user_confirmable(tmp_path):
    cfg=tmp_path/'config.yaml'; root=tmp_path/'store'
    _config(cfg); migrate_legacy_inventory(cfg, root)
    account=provision_account_instance('deepseek-web','deepseek-web:office',cfg,root)
    cp=account['connection_profile']
    assert cp['profile_id']=='cp:deepseek-web:office'
    assert cp['display_name']=='deepseek-web — office'
    assert cp['name_confirmed'] is False
    renamed=update_connection_profile_name('deepseek-web:office','DeepSeek — حساب کاری',root,confirmed=True)
    assert renamed['connection_profile']['display_name']=='DeepSeek — حساب کاری'
    assert renamed['connection_profile']['name_confirmed'] is True
    assert renamed['connection_profile']['name_source']=='user_confirmed'


def test_control_plane_exposes_connection_profile_rename_route():
    root=Path(__file__).resolve().parents[1]
    panel=(root/'control_panel.py').read_text(encoding='utf-8-sig')
    assert "/api/accounts/<path:account_id>/connection-profile" in panel
    assert 'display_name_confirmed' in panel
