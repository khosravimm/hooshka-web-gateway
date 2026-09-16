from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTROL_PANEL = ROOT / "control_panel.py"


def source() -> str:
    return CONTROL_PANEL.read_text(encoding="utf-8-sig")


def test_control_panel_exposes_provider_model_state():
    text = source()
    assert "def _provider_model_state" in text
    assert "default_upstream_model" in text
    assert "selectable_upstream_models" in text
    assert '"model": _provider_model_state(provider)' in text


def test_control_panel_has_editable_default_model_ui_and_api():
    text = source()
    assert "Default Model" in text
    assert "setProviderModel" in text
    assert "/panel/api/providers/" in text
    assert "/model" in text
    assert "@control_panel_bp.route('/api/providers/<provider_id>/model', methods=['PUT'])" in text
    assert "def api_provider_model" in text


def test_control_panel_model_update_is_validated_and_persisted():
    text = source()
    assert "default_upstream_model is required" in text
    assert "Model is not in selectable options" in text
    assert "_persist_provider_config_value(provider_id, \"default_upstream_model\", model)" in text
    assert '"success": True' in text
