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
