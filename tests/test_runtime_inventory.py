from pathlib import Path
import copy
import yaml

from core.runtime_inventory import load_runtime_configuration, load_runtime_inventory

ROOT = Path(__file__).resolve().parents[1]


def test_runtime_inventory_is_derived_from_config_and_preserves_enabled_state():
    config = yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8-sig"))
    expected = [
        (p["id"], bool(p.get("enabled", True)), p["runtime"]["cdp_url"])
        for p in config.get("providers", [])
        if (p.get("runtime") or {}).get("kind") == "chrome_cdp"
    ]
    actual = [(p["id"], p["enabled"], p["cdp_url"]) for p in load_runtime_inventory(ROOT / "config.yaml")]
    assert actual == expected


def test_runtime_orchestration_names_are_loaded_from_config():
    config = yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8-sig"))
    runtime = load_runtime_configuration(ROOT / "config.yaml")
    assert runtime["orchestration"] == config["runtime_orchestration"]


def test_runtime_inventory_rejects_duplicate_cdp_ports(tmp_path):
    config = yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8-sig"))
    runtime_providers = [p for p in config["providers"] if (p.get("runtime") or {}).get("kind") == "chrome_cdp"]
    assert len(runtime_providers) >= 2
    runtime_providers[1]["runtime"]["cdp_url"] = runtime_providers[0]["runtime"]["cdp_url"]
    path = tmp_path / "config.yaml"
    path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
    try:
        load_runtime_inventory(path)
    except ValueError as exc:
        assert "Duplicate CDP port" in str(exc)
    else:
        raise AssertionError("duplicate CDP port was accepted")


def test_shared_runtime_accepts_relative_and_absolute_same_profile(tmp_path):
    root = tmp_path
    shared = root / '.runtime-dev' / 'shared-profile'
    config = {
        'runtime_orchestration': {'shared_browser': {'enabled': True, 'cdp_url': 'http://127.0.0.1:9330', 'profile_dir': '.runtime-dev\\shared-profile'}},
        'providers': [
            {'id':'one','type':'custom','enabled':False,'runtime':{'kind':'chrome_cdp','cdp_url':'http://127.0.0.1:9330','profile_dir':'.runtime-dev\\shared-profile','home_url':'https://one.example/'}},
            {'id':'two','type':'custom','enabled':False,'runtime':{'kind':'chrome_cdp','cdp_url':'http://127.0.0.1:9330','profile_dir':str(shared),'home_url':'https://two.example/'}},
        ]
    }
    path=root/'config.yaml'; path.write_text(yaml.safe_dump(config,sort_keys=False),encoding='utf-8')
    rows=load_runtime_inventory(path)
    assert [r['id'] for r in rows]==['one','two']
    assert rows[0]['profile']==rows[1]['profile']


def test_shared_runtime_still_rejects_same_port_different_profile(tmp_path):
    config = {
        'runtime_orchestration': {'shared_browser': {'enabled': True, 'cdp_url': 'http://127.0.0.1:9330', 'profile_dir': '.runtime-dev\\shared-profile'}},
        'providers': [
            {'id':'one','runtime':{'kind':'chrome_cdp','cdp_url':'http://127.0.0.1:9330','profile_dir':'.runtime-dev\\shared-profile','home_url':'https://one.example/'}},
            {'id':'two','runtime':{'kind':'chrome_cdp','cdp_url':'http://127.0.0.1:9330','profile_dir':'.runtime-dev\\other-profile','home_url':'https://two.example/'}},
        ]
    }
    path=tmp_path/'config.yaml'; path.write_text(yaml.safe_dump(config,sort_keys=False),encoding='utf-8')
    try:
        load_runtime_inventory(path)
    except ValueError as exc:
        assert 'Duplicate CDP port' in str(exc)
    else:
        raise AssertionError('same-port different-profile conflict was accepted')


def test_production_config_isolated_from_dev_http_and_service_identity():
    prod = yaml.safe_load((ROOT / "config.production.yaml").read_text(encoding="utf-8-sig"))
    dev = yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8-sig"))
    assert dev["server"]["port"] == 5080
    assert prod["server"]["port"] == 5000
    assert prod["runtime_orchestration"]["gateway_service"] == "HooshkaWebGateway"
    assert prod["runtime_orchestration"]["gateway_health_url"] == "http://127.0.0.1:5000/health"
    assert prod["runtime_orchestration"]["restart_gateway_task"] != dev["runtime_orchestration"]["restart_gateway_task"]
    assert prod["runtime_orchestration"]["restart_all_task"] != dev["runtime_orchestration"]["restart_all_task"]


def test_production_runtime_inventory_preserves_provider_runtime_contract():
    dev = load_runtime_configuration(ROOT / "config.yaml")
    prod = load_runtime_configuration(ROOT / "config.production.yaml")
    assert [(x["id"], x["cdp_url"], x["enabled"]) for x in prod["providers"]] == [(x["id"], x["cdp_url"], x["enabled"]) for x in dev["providers"]]
