from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_single_deployment_config_path_is_honored_across_runtime_layers():
    main = (ROOT / "main.py").read_text(encoding="utf-8-sig")
    panel = (ROOT / "control_panel.py").read_text(encoding="utf-8-sig")
    inventory = (ROOT / "core/runtime_inventory.py").read_text(encoding="utf-8-sig")
    service = (ROOT / "service_manager.ps1").read_text(encoding="utf-8-sig")
    assert "HWG_CONFIG_PATH" in main
    assert "HWG_CONFIG_PATH" in panel
    assert "HWG_CONFIG_PATH" in inventory
    assert "HWG_CONFIG_PATH=$ConfigFullPath" in service
    assert "[string]$ConfigPath='config.yaml'" in service
    assert "-ConfigPath" in panel
    assert "Path(CONFIG_PATH).resolve()" in panel


def test_control_panel_no_longer_uses_local_raw_config_path_for_config_endpoints():
    panel = (ROOT / "control_panel.py").read_text(encoding="utf-8-sig")
    assert 'config_path = CONFIG_PATH' in panel
