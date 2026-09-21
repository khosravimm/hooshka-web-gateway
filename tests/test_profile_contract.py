from pathlib import Path

import yaml

from core.profile_contract import project_ng_inventory


def _write_config(path: Path, providers):
    path.write_text(yaml.safe_dump({"providers": providers}, sort_keys=False), encoding="utf-8")


def test_projection_separates_provider_profile_and_account(tmp_path):
    cfg = tmp_path / "config.yaml"
    _write_config(cfg, [{
        "id": "deepseek-web", "enabled": True,
        "runtime": {"kind": "chrome_cdp", "profile_dir": ".runtime-dev\\deepseek-profile"},
        "config": {"transport_mode": "browser_ui"},
    }])
    result = project_ng_inventory(cfg)
    assert result["contract_version"] == "1.0.0"
    assert result["provider_profiles"][0]["profile_id"] == "deepseek-web:default"
    account = result["account_instances"][0]
    assert account["provider_profile_id"] == "deepseek-web:default"
    assert account["browser_profile"]["ownership"] == "exclusive"
    assert result["conflicts"] == []


def test_projection_marks_shared_browser_profile_conflict(tmp_path):
    cfg = tmp_path / "config.yaml"
    shared = ".runtime-dev\\shared-profile"
    _write_config(cfg, [
        {"id": "chatgpt-web", "runtime": {"kind": "chrome_cdp", "profile_dir": shared}, "config": {}},
        {"id": "deepseek-web", "runtime": {"kind": "chrome_cdp", "profile_dir": shared}, "config": {}},
    ])
    result = project_ng_inventory(cfg)
    assert len(result["conflicts"]) == 1
    conflict = result["conflicts"][0]
    assert conflict["type"] == "shared_browser_profile"
    assert set(conflict["providers"]) == {"chatgpt-web", "deepseek-web"}
    assert all(a["browser_profile"]["ownership"] == "shared_conflict" for a in result["account_instances"])
    assert result["migration_complete"] is False
