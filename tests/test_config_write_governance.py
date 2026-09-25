import copy
from pathlib import Path

import yaml

import control_panel


def _client():
    from flask import Flask
    app = Flask(__name__)
    app.register_blueprint(control_panel.control_panel_bp)
    return app.test_client()


def _baseline():
    return yaml.safe_load(Path("config.yaml").read_text(encoding="utf-8-sig"))


def test_config_summary_rejects_invalid_port_without_saving(monkeypatch):
    cfg = _baseline()
    saved = []
    restarted = []
    monkeypatch.setattr(control_panel, "_load_config_file", lambda: copy.deepcopy(cfg))
    monkeypatch.setattr(control_panel, "_save_config_file", lambda value: saved.append(value))
    monkeypatch.setattr(control_panel, "_schedule_restart_all", lambda reason: restarted.append(reason))
    response = _client().put("/panel/api/config/summary", json={"server": {"port": 70000}})
    assert response.status_code == 400
    assert "server.port" in response.get_json()["error"]
    assert saved == []
    assert restarted == []


def test_config_summary_cannot_bypass_provider_readiness_gate(monkeypatch):
    cfg = _baseline()
    target = next(p for p in cfg["providers"] if p["id"] == "zai-web")
    target["enabled"] = False
    saved = []
    monkeypatch.setattr(control_panel, "_load_config_file", lambda: copy.deepcopy(cfg))
    monkeypatch.setattr(control_panel, "_save_config_file", lambda value: saved.append(value))
    monkeypatch.setattr(control_panel, "load_readiness", lambda provider_id: {"state": "FEATURE_INVALID", "ready": False, "current": False})
    response = _client().put("/panel/api/config/summary", json={"providers": [{"id": "zai-web", "enabled": True}]})
    assert response.status_code == 400
    assert "provider_enable_requires_current_readiness" in response.get_json()["error"]
    assert saved == []


def test_raw_config_rejects_non_mapping_without_write(tmp_path, monkeypatch):
    path = tmp_path / "config.yaml"
    path.write_text(yaml.safe_dump(_baseline(), sort_keys=False), encoding="utf-8")
    monkeypatch.setattr(control_panel, "CONFIG_PATH", str(path))
    response = _client().put("/panel/api/config", json={"content": "- not\n- a\n- mapping\n"})
    assert response.status_code == 400
    assert "root must be a mapping" in response.get_json()["error"].lower()
    assert isinstance(yaml.safe_load(path.read_text(encoding="utf-8")), dict)


def test_raw_config_rejects_stale_provider_enable_without_write(tmp_path, monkeypatch):
    cfg = _baseline()
    next(p for p in cfg["providers"] if p["id"] == "zai-web")["enabled"] = False
    path = tmp_path / "config.yaml"
    path.write_text(yaml.safe_dump(cfg, sort_keys=False), encoding="utf-8")
    candidate = copy.deepcopy(cfg)
    next(p for p in candidate["providers"] if p["id"] == "zai-web")["enabled"] = True
    monkeypatch.setattr(control_panel, "CONFIG_PATH", str(path))
    monkeypatch.setattr(control_panel, "load_readiness", lambda provider_id: {"state": "FEATURE_INVALID", "ready": False, "current": False})
    response = _client().put("/panel/api/config", json={"content": yaml.safe_dump(candidate, sort_keys=False)})
    assert response.status_code == 400
    assert "provider_enable_requires_current_readiness" in response.get_json()["error"]
    stored = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert next(p for p in stored["providers"] if p["id"] == "zai-web")["enabled"] is False


def test_current_config_passes_shared_candidate_validation():
    cfg = _baseline()
    control_panel._validate_config_candidate(cfg, previous=copy.deepcopy(cfg))

def test_config_summary_rejects_values_above_ui_bounds(monkeypatch):
    cfg = _baseline()
    saved = []
    restarted = []
    monkeypatch.setattr(control_panel, "_load_config_file", lambda: copy.deepcopy(cfg))
    monkeypatch.setattr(control_panel, "_save_config_file", lambda value: saved.append(value))
    monkeypatch.setattr(control_panel, "_schedule_restart_all", lambda reason: restarted.append(reason))
    cases = [
        ({"server": {"threads": 129}}, "server.threads"),
        ({"server": {"provider_concurrency": 33}}, "server.provider_concurrency"),
        ({"cdp": {"timeout": 300001}}, "cdp.timeout"),
    ]
    for payload, marker in cases:
        response = _client().put("/panel/api/config/summary", json=payload)
        assert response.status_code == 400
        assert marker in response.get_json()["error"]
    assert saved == []
    assert restarted == []

