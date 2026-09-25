from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTROL_PANEL = ROOT / "control_panel.py"
UI_DIR = ROOT / "control_panel_ui"
INDEX = UI_DIR / "index.html"
CSS = UI_DIR / "panel.css"
JS = UI_DIR / "panel.js"


def source() -> str:
    return CONTROL_PANEL.read_text(encoding="utf-8-sig")


def index_text() -> str:
    return INDEX.read_text(encoding="utf-8-sig")


def css_text() -> str:
    return CSS.read_text(encoding="utf-8-sig")


def js_text() -> str:
    return JS.read_text(encoding="utf-8-sig")


def test_control_panel_exposes_provider_model_state():
    text = source()
    assert "def _provider_model_state" in text
    assert "default_upstream_model" in text
    assert "selectable_upstream_models" in text
    assert '"model": _provider_model_state(provider)' in text


def test_control_panel_has_editable_default_model_ui_and_api():
    text = source()
    assert "@control_panel_bp.route('/api/providers/<provider_id>/model', methods=['PUT'])" in text
    assert "def api_provider_model" in text
    js = js_text()
    assert "HwgModelSave" in js
    assert "model-${p.id}" in js
    assert "/model" in js


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
    assert 'inventory_by_id(CONFIG_PATH).get(provider_id)' in block
    assert 'runtime_cfg["cdp_url"]' in block
    assert "provider.health_check" not in block
    assert '"check": "cdp_runtime"' in block
    assert "duration_ms" in block
    js = js_text()
    assert "HwgTestProvider" in js
    assert "test-status-" in js
    assert "finally" in js


def test_config_declares_selectable_upstream_models_for_model_picker():
    cfg = (ROOT / "config.yaml").read_text(encoding="utf-8-sig")
    assert "selectable_upstream_models:" in cfg
    assert "qwen3.7-plus" in cfg
    assert "qwen3.8-max" in cfg
    assert "glm-5.3" in cfg
    assert "glm-5.3-flash" in cfg


def test_control_panel_request_chart_has_operational_axes():
    js = js_text()
    assert "function niceCeil" in js
    assert "labelStep" in js
    assert "\u062f\u0631 \u06cc\u06a9 \u0633\u0627\u0639\u062a \u06af\u0630\u0634\u062a\u0647 \u0627\u0631\u0633\u0627\u0644 \u0648\u0627\u0642\u0639\u06cc \u0628\u0647 Provider \u062b\u0628\u062a \u0646\u0634\u062f\u0647 \u0627\u0633\u062a" in js
    text = source()
    assert "def _build_request_history_window" in text


def test_control_panel_stats_builds_continuous_sixty_minute_window():
    text = source()
    assert "def _build_request_history_window" in text
    assert "minutes=60" in text
    assert "minute_counts = {start_minute + (i * 60): 0 for i in range(minutes)}" in text
    assert "start_minute <= minute <= end_minute" in text
    assert "return jsonify(_build_request_history_window())" in text


def test_control_panel_uses_select_for_default_model_picker():
    js = js_text()
    assert '<select class="ctrl" id="model-${p.id}"' in js
    assert "<option value=" in js
    assert 'input id="model-${p.id}"' not in js
    assert 'datalist' not in js
    text = source()
    assert "selectable_upstream_models" in text


def test_control_panel_wraps_capability_badges_to_reduce_horizontal_scroll():
    js = js_text()
    assert "capability-badges" in js
    css = css_text()
    assert ".capability-badges { display: flex; flex-wrap: wrap;" in css
    assert ".capability-badges span" in css or ".cap-badge" in css


def test_control_panel_providers_use_relationship_cards_not_dense_table():
    index = index_text()
    assert "panel-providers" in index
    assert "providers-grid" in index
    assert "providers-body" not in index
    js = js_text()
    assert "provider-relationship-card" in js
    assert "HwgGoAccounts" in js
    assert "پس از READY قابل فعال‌سازی" in js


def test_control_panel_service_tab_uses_structured_windows_service_status():
    text = source()
    assert "def _service_names()" in text
    assert "load_orchestration_settings(CONFIG_PATH)" in text
    assert 'settings["gateway_service"]' in text
    assert 'settings.get("legacy_gateway_service")' in text
    assert "def _query_windows_service" in text
    assert "Get-Service -Name" in text
    assert "ConvertTo-Json -Compress" in text
    assert "def _service_status_payload" in text
    index = index_text()
    assert "svc-start" in index and "svc-stop" in index and "svc-restart" in index
    js = js_text()
    assert "loadServiceStatus" in js


def test_control_panel_service_tab_maps_payload_to_ui_elements():
    index = index_text()
    assert "svc-status-text" in index
    assert "svc-start-type" in index
    assert "svc-can-stop" in index
    assert "svc-legacy" in index
    assert "svc-service-type" in index
    js = js_text()
    assert "svc-status-text" in js
    assert "svc-start-type" in js
    assert "svc-can-stop" in js
    assert "svc-legacy" in js
    assert "service-info" not in js
    assert "JSON.stringify(data, null, 2)" not in js
    assert "if (name === 'service') loadServiceStatus();" in js


def test_control_panel_overview_has_model_usage_summary():
    index = index_text()
    assert "model-usage-summary" in index
    js = js_text()
    assert "renderModelUsage" in js
    assert "api('/model_usage')" in js
    text = source()
    assert "def api_model_usage" in text
    assert "prompt_tokens" in text and "completion_tokens" in text and "total_tokens" in text


def test_control_panel_config_has_human_settings_and_advanced_yaml():
    index = index_text()
    assert "cfg-server-host" in index
    assert "cfg-cdp-url" not in index
    assert "cfg-auth-enabled" in index
    assert "config-providers" in index
    assert "cfg-provider-cdp-" not in js_text()
    assert "cfg-provider-enabled-" not in js_text()
    js = js_text()
    assert "saveHumanConfig" in js
    assert "saveRawConfig" in js
    assert "/config/summary" in js
    assert "/config/" in js
    text = source()
    assert "Configuration (config.yaml)" not in text


def test_control_panel_config_summary_backend_exists():
    text = source()
    assert "def _config_summary_from_dict" in text
    assert "def _apply_config_summary" in text
    assert "def api_config_summary" in text


def legacy_removed_model_usage_includes_zero_rows_for_configured_providers():
    text = source()
    assert "no_measured_traffic" in text
    assert "ensure_row(provider.provider_id" not in text
    assert "Zero-request rows" in Path("CHANGELOG.md").read_text(encoding="utf-8") or "fabricate" in Path("CHANGELOG.md").read_text(encoding="utf-8")


def test_model_usage_does_not_fabricate_zero_rows():
    text = source()
    assert "Do not fabricate zero-request rows as statistics" in text
    assert "no_measured_traffic" in text
    assert '"status": "measured" if rows else "no_measured_traffic"' in text
    assert "monitored" in text
    assert "ensure_row(provider.provider_id" not in text
    js = js_text()
    assert "ترافیک مدل تکمیل" in js or "۱ ساعت گذشته" in js


def test_model_usage_uses_field_level_token_availability():
    text = source()
    assert "prompt_tokens_available" in text
    assert "completion_tokens_available" in text
    assert "total_tokens_available" in text
    js = js_text()
    assert "prompt_tokens_available" in js
    assert "tokens_estimated" in js
    assert "در دسترس نیست" in js


def test_model_usage_uses_human_labels_and_compact_grid():
    js = js_text()
    assert "درخواست" in js
    assert "توکن ورودی" in js
    assert "توکن خروجی" in js
    assert "کل توکن" in js
    assert "در دسترس نیست" in js
    assert "${r.requests} req" not in js
    index = index_text()
    assert "model-usage-summary" in index


def test_model_accounting_uses_compact_number_formatting():
    js = js_text()
    assert "function compact" in js
    assert "+ 'B'" in js
    assert "+ 'M'" in js
    assert "+ 'k'" in js
    assert "compact(r.requests)" in js


def test_control_panel_dashboard_uses_provider_bound_traffic_only():
    js = js_text()
    assert "api('/stats')" in js
    assert "renderOutboundKpis" in js
    index = index_text()
    assert "ارسال واقعی به Web Chat" in index
    assert "outbound-kpis" in index
    text = source()
    assert "def _request_bucket" in text
    assert 'provider in ("", "unknown", "default")' in text
    assert "Do not fabricate zero-request rows as statistics" in text


def test_model_accounting_reports_unavailable_when_no_tokens_captured():
    js = js_text()
    assert "tokens_estimated" in js
    assert "در دسترس نیست" in js
    text = source()
    assert "tokens_available" in text

def test_control_panel_renders_only_active_workspace():
    css = css_text()
    assert ".panel { display: none; min-width: 0; }" in css
    assert ".panel.active { display: block; }" in css
    index = index_text()
    assert index.count('<section class="panel active"') == 1
    assert 'data-panel="overview"' in index
    js = js_text()
    assert "p.classList.toggle('active', p.id === 'panel-' + name)" in js


def test_operational_ui_separates_provider_config_from_browser_runtime():
    js = js_text()
    index = index_text()
    assert "HwgProviderEnabled" in js
    assert "HwgRuntimeProfile" in js
    assert "HwgGoRuntime" in js
    assert "HwgProviderProfile" not in js
    assert "مرورگر و اتصال" in index
    assert "زنجیره آماده‌سازی Web Chat" in index
    assert 'id="profiles-grid"' in index
    assert 'id="profile-create"' in index
    text = source()
    assert "def api_provider_settings" in text
    assert "def api_runtime_profiles" in text
    assert "def api_runtime_profile_delete_by_path" in text
    assert "def api_runtime_orchestration" in text
