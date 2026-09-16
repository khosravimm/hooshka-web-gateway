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
    assert 'capability-badges' in text
    assert '#providers-table .capability-badges{display:flex;flex-wrap:wrap' in text
    assert '#providers-table .capability-badges span{white-space:normal' in text


def test_control_panel_providers_table_prevents_horizontal_overflow():
    text = source()
    assert '#providers-table{overflow-x:hidden}' in text
    assert '#providers-table table{table-layout:fixed;width:100%;min-width:0}' in text
    assert '<colgroup>' in text
    assert 'provider-capabilities-col' in text
    assert 'capability-badges' in text
    assert 'runtime-url' in text


def test_control_panel_service_tab_uses_structured_windows_service_status():
    text = source()
    assert 'SERVICE_NAME = "HooshkaWebGateway"' in text
    assert 'LEGACY_SERVICE_NAME = "WebLLMBridge"' in text
    assert 'def _query_windows_service' in text
    assert 'Get-Service -Name' in text
    assert 'ConvertTo-Json -Compress' in text
    assert 'def _service_status_payload' in text
    assert 'Canonical service:' in text
    assert 'svc-start' in text and 'svc-stop' in text and 'svc-restart' in text
    assert "if (tabName === 'service') loadServiceStatus();" in text


def test_control_panel_service_tab_maps_payload_to_ui_elements():
    text = source()
    assert 'service-summary' in text
    assert 'svc-status-text' in text
    assert 'svc-start-type' in text
    assert 'svc-can-stop' in text
    assert 'svc-legacy' in text
    assert 'Raw service-manager output' in text
    assert 'service-info' not in text
    assert "JSON.stringify(data, null, 2)" not in text


def test_control_panel_overview_has_model_usage_summary():
    text = source()
    assert 'Model Traffic & Token Accounting (1h)' in text
    assert 'model-usage-summary' in text
    assert "api('/model_usage')" in text
    assert 'updateModelUsage' in text
    assert 'not captured' in text
    assert 'def api_model_usage' in text
    assert 'prompt_tokens' in text and 'completion_tokens' in text and 'total_tokens' in text


def test_control_panel_config_has_human_settings_and_advanced_yaml():
    text = source()
    assert 'Human Settings' in text
    assert 'cfg-server-host' in text
    assert 'cfg-cdp-url' in text
    assert 'cfg-auth-enabled' in text
    assert 'config-providers' in text
    assert 'Advanced Raw YAML' in text
    assert 'saveHumanConfig' in text
    assert 'saveRawConfig' in text
    assert "/api/config/summary" in text
    assert 'Configuration (config.yaml)' not in text


def test_control_panel_config_summary_backend_exists():
    text = source()
    assert 'def _config_summary_from_dict' in text
    assert 'def _apply_config_summary' in text
    assert 'def api_config_summary' in text


def legacy_removed_model_usage_includes_zero_rows_for_configured_providers():
    text = source()
    assert 'Always include configured providers' in text
    assert 'provider_registry.list_providers(enabled_only=False)' in text
    assert 'ensure_row(provider.provider_id' in text
    assert 'Zero-request rows' in Path('CHANGELOG.md').read_text(encoding='utf-8')


def test_model_usage_does_not_fabricate_zero_rows():
    text = source()
    assert 'Do not fabricate zero-request rows as statistics' in text
    assert 'no_measured_traffic' in text
    assert 'monitored' in text
    assert 'No measured model traffic in the last hour.' in text
    assert 'ensure_row(provider.provider_id' not in text


def test_model_usage_uses_field_level_token_availability():
    text = source()
    assert 'prompt_tokens_available' in text
    assert 'completion_tokens_available' in text
    assert 'total_tokens_available' in text
    assert "tokenValue(r.prompt_tokens, promptAvailable)" in text
    assert "not captured" in text


def test_model_usage_uses_human_labels_and_compact_grid():
    text = source()
    assert 'Model Traffic & Token Accounting (1h)' in text
    assert 'grid grid-cols-1 md:grid-cols-2 gap-3 text-sm' in text
    assert 'Requests: ${formatCompactNumber(r.requests)}' in text
    assert 'Input tokens' in text
    assert 'Output tokens' in text
    assert 'Total tokens' in text
    assert 'not captured' in text
    assert '${r.requests} req' not in text
    assert '>Prompt<' not in text
    assert '>Completion<' not in text


def test_model_accounting_uses_compact_number_formatting():
    text = source()
    assert 'function formatCompactNumber' in text
    assert " + 'B'" in text
    assert " + 'M'" in text
    assert " + 'k'" in text
    assert 'Requests: ${formatCompactNumber(r.requests)}' in text
    assert 'formatCompactNumber(value)' in text
    assert 'fullValue(r.total_tokens, totalAvailable)' in text
