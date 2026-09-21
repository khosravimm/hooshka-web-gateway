import json
from pathlib import Path

import pytest
import yaml

from core.profile_store import load_ng_inventory, load_persistent_inventory, migrate_legacy_inventory, rollback_legacy_migration, reconcile_isolation_metadata


def _config(path: Path, providers):
    path.write_text(yaml.safe_dump({"providers": providers}, sort_keys=False), encoding="utf-8")


def _provider(pid, profile, home_url=None):
    return {
        "id": pid,
        "enabled": True,
        "runtime": {"kind":"chrome_cdp", "profile_dir":profile, **({"home_url":home_url} if home_url else {})},
        "config": {"transport_mode":"browser_ui"},
    }


def test_migration_persists_profiles_and_accounts_separately(tmp_path):
    cfg=tmp_path/'config.yaml'; root=tmp_path/'store'
    _config(cfg,[_provider('deepseek-web','.runtime-dev/deepseek-profile')])
    inv=migrate_legacy_inventory(cfg,root)
    assert inv['authority']=='persistent_ng_store'
    assert len(list((root/'provider_profiles').glob('*.json')))==1
    assert len(list((root/'account_instances').glob('*.json')))==1
    profile=inv['provider_profiles'][0]; account=inv['account_instances'][0]
    assert profile['artifact_version'] and account['artifact_version']
    assert profile['change_log'] and account['change_log']


def test_persistent_store_becomes_ng_authority(tmp_path):
    cfg=tmp_path/'config.yaml'; root=tmp_path/'store'
    _config(cfg,[_provider('deepseek-web','.runtime-dev/deepseek-profile')])
    migrate_legacy_inventory(cfg,root)
    _config(cfg,[_provider('changed-provider','.runtime-dev/changed-profile')])
    inv=load_ng_inventory(cfg,root)
    assert inv['authority']=='persistent_ng_store'
    assert [x['provider_id'] for x in inv['provider_profiles']]==['deepseek-web']


def test_cross_origin_shared_profile_is_not_conflict_after_persistence(tmp_path):
    cfg=tmp_path/'config.yaml'; root=tmp_path/'store'; shared='.runtime-dev/shared-profile'
    _config(cfg,[
        _provider('chatgpt-web',shared,'https://chatgpt.com/'),
        _provider('deepseek-web',shared,'https://chat.deepseek.com/'),
    ])
    inv=migrate_legacy_inventory(cfg,root)
    assert inv['migration_complete'] is True
    assert inv['conflicts']==[]
    assert {a['browser_profile']['sharing_mode'] for a in inv['account_instances']}=={'cross_origin_isolated'}


def test_same_origin_shared_profile_remains_conflict(tmp_path):
    cfg=tmp_path/'config.yaml'; root=tmp_path/'store'; shared='.runtime-dev/shared-profile'
    _config(cfg,[
        _provider('chatgpt-a',shared,'https://chatgpt.com/'),
        _provider('chatgpt-b',shared,'https://chatgpt.com/'),
    ])
    inv=migrate_legacy_inventory(cfg,root)
    assert len(inv['conflicts'])==1
    assert inv['conflicts'][0]['scope']=='same_origin'
    assert inv['conflicts'][0]['origin']=='https://chatgpt.com'


def test_migration_is_reversible_when_artifacts_unchanged(tmp_path):
    cfg=tmp_path/'config.yaml'; root=tmp_path/'store'
    _config(cfg,[_provider('deepseek-web','.runtime-dev/deepseek-profile')])
    migrate_legacy_inventory(cfg,root)
    result=rollback_legacy_migration(root)
    assert result['rolled_back'] is True
    inv=load_ng_inventory(cfg,root)
    assert inv['authority']=='legacy_projection'


def test_rollback_refuses_to_delete_changed_artifact(tmp_path):
    cfg=tmp_path/'config.yaml'; root=tmp_path/'store'
    _config(cfg,[_provider('deepseek-web','.runtime-dev/deepseek-profile')])
    migrate_legacy_inventory(cfg,root)
    artifact=next((root/'provider_profiles').glob('*.json'))
    data=json.loads(artifact.read_text(encoding='utf-8'))
    data['operator_note']='changed after migration'
    artifact.write_text(json.dumps(data),encoding='utf-8')
    with pytest.raises(RuntimeError,match='artifact changed after migration'):
        rollback_legacy_migration(root)
    assert artifact.exists()


def test_migrated_artifacts_do_not_persist_secret_values(tmp_path):
    cfg=tmp_path/'config.yaml'; root=tmp_path/'store'
    p=_provider('deepseek-web','.runtime-dev/deepseek-profile')
    p['config']['api_key']='DO_NOT_COPY_ME'
    _config(cfg,[p])
    migrate_legacy_inventory(cfg,root)
    raw=''.join(x.read_text(encoding='utf-8') for x in root.rglob('*.json'))
    assert 'DO_NOT_COPY_ME' not in raw


def test_control_plane_uses_persistent_inventory_and_guarded_migration_routes():
    src=Path('control_panel.py').read_text(encoding='utf-8-sig')
    assert 'return jsonify(load_ng_inventory(CONFIG_PATH))' in src
    assert "/api/ng/migrate" in src and "/api/ng/rollback" in src
    assert 'Persistent NG migration requires confirm=true' in src
    assert 'NG migration rollback requires confirm=true' in src


def test_reconcile_isolation_metadata_preserves_session(tmp_path):
    cfg=tmp_path/'config.yaml'; root=tmp_path/'store'; shared='.runtime-dev/shared-profile'
    _config(cfg,[
        _provider('chatgpt-web',shared,'https://chatgpt.com/'),
        _provider('deepseek-web',shared,'https://chat.deepseek.com/'),
    ])
    inv=migrate_legacy_inventory(cfg,root)
    account_path=next((root/'account_instances').glob('chatgpt-web__default-account.json'))
    data=json.loads(account_path.read_text(encoding='utf-8'))
    data['browser_profile'].pop('origin',None); data['browser_profile'].pop('sharing_mode',None)
    data['session']={'state':'authenticated','access_state':'AUTHENTICATED','validated_at':'x'}
    account_path.write_text(json.dumps(data),encoding='utf-8')
    out=reconcile_isolation_metadata(cfg,root)
    account=next(a for a in out['account_instances'] if a['account_id']=='chatgpt-web:default-account')
    assert account['session']['access_state']=='AUTHENTICATED'
    assert account['browser_profile']['origin']=='https://chatgpt.com'
    assert account['browser_profile']['sharing_mode']=='cross_origin_isolated'
    assert out['conflicts']==[]


def test_control_plane_has_guarded_isolation_reconciliation_route():
    src=Path('control_panel.py').read_text(encoding='utf-8-sig')
    assert '/api/ng/reconcile-isolation' in src
    assert 'Isolation metadata reconciliation requires confirm=true' in src
