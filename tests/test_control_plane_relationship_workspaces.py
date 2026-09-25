from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
HTML=(ROOT/'control_panel_ui/index.html').read_text(encoding='utf-8-sig')
JS=(ROOT/'control_panel_ui/panel.js').read_text(encoding='utf-8-sig')


def test_accounts_profiles_runtimes_discovery_are_distinct_workspaces():
    for panel in ('panel-runtimes','panel-profiles','panel-accounts','panel-discovery'):
        assert f'id="{panel}"' in HTML
    assert 'data-panel="profiles"' not in HTML
    assert 'پروفایل‌های مرورگر (فنی)' in HTML
    assert 'فراهم‌کننده‌ها و پروفایل‌ها' in HTML
    assert 'data-panel="accounts"' in HTML
    runtime=HTML[HTML.index('id="panel-runtimes"'):HTML.index('id="panel-profiles"')]
    assert 'id="profiles-grid"' not in runtime


def test_account_workspace_exposes_relationship_and_verified_actions():
    assert 'پروفایل اتصال' in HTML
    assert 'Connection Profiles' in JS
    assert 'connection_profile' in JS
    assert 'async function loadAccounts()' in JS
    assert "data-aa=\"validate\"" in JS
    assert "data-aa=\"login\"" in JS
    assert "data-aa=\"reauth\"" in JS
    assert "data-aa=\"logout\"" in JS
    assert "راستی‌آزمایی پس از عملیات" in JS
    assert "/accounts/'+encodeURIComponent(accountId)+'/session" in JS


def test_profile_workspace_exposes_isolation_modes():
    assert 'async function loadProfiles()' in JS
    assert 'cross_origin_isolated' in JS
    assert 'same_origin_conflict' in JS
    assert 'Cross-origin isolated' in JS
