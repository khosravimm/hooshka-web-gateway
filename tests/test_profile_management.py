from pathlib import Path

import pytest

import control_panel


def test_profile_path_rejects_escape(tmp_path, monkeypatch):
    root = tmp_path / ".runtime-dev"
    monkeypatch.setattr(control_panel, "_profile_root", lambda: root.resolve())
    with pytest.raises(ValueError):
        control_panel._safe_profile_path(tmp_path / "outside-profile")


def test_profile_path_accepts_managed_runtime_path(tmp_path, monkeypatch):
    root = tmp_path / ".runtime-dev"
    monkeypatch.setattr(control_panel, "_profile_root", lambda: root.resolve())
    target = root / "profiles" / "demo"
    assert control_panel._safe_profile_path(target) == target.resolve()


def _client():
    from flask import Flask
    app = Flask(__name__)
    app.register_blueprint(control_panel.control_panel_bp)
    app.testing = True
    return app.test_client()


def test_provider_settings_persists_enabled_and_profile(tmp_path, monkeypatch):
    cfg = {"providers": [{"id": "deepseek-web", "enabled": True, "priority": 70, "runtime": {"profile_dir": ".runtime-dev\\shared-profile"}, "config": {}}]}
    saved = {}
    root = tmp_path / ".runtime-dev"
    monkeypatch.setattr(control_panel, "_profile_root", lambda: root.resolve())
    monkeypatch.setattr(control_panel, "_profile_relative", lambda path: ".runtime-dev\\profiles\\ds")
    monkeypatch.setattr(control_panel, "_load_config_file", lambda: cfg)
    monkeypatch.setattr(control_panel, "_save_config_file", lambda value: saved.update(value))
    monkeypatch.setattr(control_panel, "_schedule_restart_all", lambda reason: {"scheduled": True, "reason": reason})
    monkeypatch.setattr(control_panel.provider_registry, "get", lambda provider_id: None)
    response = _client().put('/panel/api/providers/deepseek-web/settings', json={"enabled": False, "profile_dir": str(root / "profiles" / "ds")})
    assert response.status_code == 200
    assert cfg["providers"][0]["enabled"] is False
    assert cfg["providers"][0]["runtime"]["profile_dir"].endswith("profiles\\ds")
    assert (root / "profiles" / "ds").is_dir()


def test_assigned_managed_profile_cannot_be_deleted(tmp_path, monkeypatch):
    root = tmp_path / ".runtime-dev"
    target = root / "profiles" / "used"
    target.mkdir(parents=True)
    cfg = {"providers": [{"id": "qwen-web", "runtime": {"profile_dir": str(target)}}]}
    monkeypatch.setattr(control_panel, "_profile_root", lambda: root.resolve())
    monkeypatch.setattr(control_panel, "_load_config_file", lambda: cfg)
    response = _client().delete('/panel/api/runtime/profiles/used')
    assert response.status_code == 409
    assert target.exists()
    assert response.get_json()["assigned_to"] == ["qwen-web"]
