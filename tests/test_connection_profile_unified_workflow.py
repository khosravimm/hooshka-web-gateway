from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def test_account_runtime_is_first_class_explorer_target():
    panel=(ROOT/'control_panel.py').read_text(encoding='utf-8-sig')
    assert '"scope": "account"' in panel
    assert '"account_id": account.get("account_id")' in panel
    assert '"connection_profile_name": cp.get("display_name")' in panel
    assert 'load_ng_inventory(CONFIG_PATH)' in panel


def test_exact_scope_certification_is_read_only_ui_metadata():
    panel=(ROOT/'control_panel.py').read_text(encoding='utf-8-sig')
    js=(ROOT/'control_panel_ui/panel.js').read_text(encoding='utf-8-sig')
    assert "/api/provider-certification-matrix" in panel
    assert "HWG_PROVIDER_CERTIFICATION_MATRIX_V1.json" in panel
    assert "certRows.find" in js
    assert "certLabel" in js


def test_connection_profile_creation_opens_isolated_login_flow():
    js=(ROOT/'control_panel_ui/panel.js').read_text(encoding='utf-8-sig')
    assert "HwgCreateConnectionProfile" in js
    assert "'/runtime/start'" in js
    assert "'/login/open'" in js


def test_existing_connection_profile_can_continue_in_explorer():
    js=(ROOT/'control_panel_ui/panel.js').read_text(encoding='utf-8-sig')
    assert "HwgExploreConnection" in js
    assert "recommended_runtime_key:runtime.runtime_key" in js
    assert "r.scope==='provider'" in js
    assert "r.representative_provider===providerId" in js
    assert "providerWizard.connectionProfile" in js
    assert "cp.account_id" in js
    assert "cp?.access_state" in js




def test_default_connection_profiles_have_human_readable_fallback_names():
    js=(ROOT/'control_panel_ui/panel.js').read_text(encoding='utf-8-sig')
    assert 'function connectionDisplayName' in js
    assert "'chatgpt-web':'ChatGPT'" in js
    assert "'deepseek-web':'DeepSeek'" in js
    assert "leaf==='default-account'" in js
    assert 'حساب اصلی' in js


def test_provider_workspace_hides_raw_runtime_until_technical_details():
    js=(ROOT/'control_panel_ui/panel.js').read_text(encoding='utf-8-sig')
    assert "const runtimeLabel=rt.cdp_url ? 'اختصاصی این حساب' : 'مشترک Provider'" in js
    assert '<summary>جزئیات فنی</summary>' in js
    assert 'CDP: ${esc(rt.cdp_url' in js


def test_secondary_account_cannot_accidentally_run_provider_level_readiness():
    js=(ROOT/'control_panel_ui/panel.js').read_text(encoding='utf-8-sig')
    assert "providerProbeOwnsAccount=a.account_id===providerId+':default-account'" in js
    assert 'Readiness حساب اختصاصی باید با Probe حساب‌محور اجرا شود' in js
