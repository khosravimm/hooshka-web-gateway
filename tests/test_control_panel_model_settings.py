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


def test_control_panel_provider_test_is_fast_runtime_probe():
    text = source()
    marker = "def api_test_provider(provider_id):"
    assert marker in text
    block = text.split(marker, 1)[1].split("@control_panel_bp.route('/api/sessions", 1)[0]
    assert '_check_cdp(provider.config.config.get("cdp_url"))' in block
    assert "provider.health_check" not in block
    assert '"check": "cdp_runtime"' in block
    assert "duration_ms" in block
    assert "AbortController" in text
    assert "finally" in text
    assert "test-status-" in text


def test_config_declares_selectable_upstream_models_for_model_picker():
    cfg = (ROOT / "config.yaml").read_text(encoding="utf-8-sig")
    assert "selectable_upstream_models:" in cfg
    assert "qwen3.7-plus" in cfg
    assert "qwen3.8-max" in cfg
    assert "glm-5.3" in cfg
    assert "glm-5.3-flash" in cfg


def test_control_panel_request_chart_has_operational_axes():
    text = source()
    assert "function niceCeil" in text
    assert "function formatChartTime" in text
    assert "Requests per minute" in text
    assert "const yTicks = 5" in text
    assert "labelStep" in text
    assert "No recent request data" in text
    assert "max " in text
    assert "points.length > 45" in text


def test_control_panel_stats_builds_continuous_sixty_minute_window():
    text = source()
    assert "def _build_request_history_window" in text
    assert "minutes=60" in text
    assert "minute_counts = {start_minute + (i * 60): 0 for i in range(minutes)}" in text
    assert "start_minute <= minute <= end_minute" in text
    assert "return jsonify(_build_request_history_window())" in text


def test_control_panel_uses_select_for_default_model_picker():
    text = source()
    assert '<select id="model-${p.id}"' in text
    assert '<option value="${m}"' in text
    assert 'input id="model-${p.id}"' not in text
    assert 'datalist id="model-options-${p.id}"' not in text
    assert 'current: <span class="font-mono">${p.model?.default || p.id}</span>' in text


def test_control_panel_wraps_capability_badges_to_reduce_horizontal_scroll():
    text = source()
    assert 'flex flex-wrap gap-1 max-w-xs' in text
    assert 'whitespace-nowrap' in text
    assert 'max-w-xs' in text
