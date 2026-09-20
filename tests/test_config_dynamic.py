import pytest

from core.config import get_default_config, load_config


def test_default_config_has_no_providers():
    d = get_default_config()
    assert d["providers"] == []
    assert "chatgpt" not in d


def test_default_config_rate_governance_empty():
    d = get_default_config()
    assert d["governance"]["rate_limiting"]["per_provider"] == {}
    assert d["governance"]["rate_limiting"]["default_requests_per_minute"] == 60


def test_load_config_raises_when_file_missing():
    with pytest.raises(FileNotFoundError):
        load_config("no-such-config-file.yaml")


def test_load_config_declared_providers_preserved(tmp_path):
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text(
        "server:\n  host: 127.0.0.1\n  port: 5099\nproviders:\n"
        "  - id: zai-web\n    type: zai_web\n    enabled: true\n"
        "    config:\n      base_url: https://chat.z.ai\n"
        "governance:\n  rate_limiting:\n    per_provider:\n"
        "      zai-web:\n        requests_per_minute: 7\n",
        encoding="utf-8",
    )
    cfg = load_config(str(cfg_path))
    assert cfg["server"]["port"] == 5099
    assert [p["id"] for p in cfg["providers"]] == ["zai-web"]
    assert cfg["governance"]["rate_limiting"]["per_provider"]["zai-web"]["requests_per_minute"] == 7