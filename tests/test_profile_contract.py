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


def test_projection_allows_cross_origin_shared_profile(tmp_path):
    cfg = tmp_path / "config.yaml"
    shared = ".runtime-dev\\shared-profile"
    _write_config(cfg, [
        {"id":"chatgpt-web","runtime":{"kind":"chrome_cdp","profile_dir":shared,"home_url":"https://chatgpt.com/"},"config":{}},
        {"id":"deepseek-web","runtime":{"kind":"chrome_cdp","profile_dir":shared,"home_url":"https://chat.deepseek.com/"},"config":{}},
    ])
    result=project_ng_inventory(cfg)
    assert result["conflicts"] == []
    accounts=result["account_instances"]
    assert all(a["browser_profile"]["ownership"]=="origin_isolated_shared" for a in accounts)
    assert all(a["browser_profile"]["sharing_mode"]=="cross_origin_isolated" for a in accounts)
    assert {a["browser_profile"]["origin"] for a in accounts}=={"https://chatgpt.com","https://chat.deepseek.com"}


def test_projection_blocks_same_origin_shared_profile(tmp_path):
    cfg=tmp_path/'config.yaml'; shared='.runtime-dev\\shared-profile'
    _write_config(cfg,[
        {"id":"chatgpt-a","runtime":{"kind":"chrome_cdp","profile_dir":shared,"home_url":"https://chatgpt.com/"},"config":{}},
        {"id":"chatgpt-b","runtime":{"kind":"chrome_cdp","profile_dir":shared,"home_url":"https://chatgpt.com/"},"config":{}},
    ])
    result=project_ng_inventory(cfg)
    assert len(result["conflicts"])==1
    conflict=result["conflicts"][0]
    assert conflict["scope"]=="same_origin"
    assert conflict["origin"]=="https://chatgpt.com"
    assert all(a["browser_profile"]["sharing_mode"]=="same_origin_conflict" for a in result["account_instances"])
