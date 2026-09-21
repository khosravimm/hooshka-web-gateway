"""Unit tests for SharedBrowserPool (mocked CDP HTTP, no live browser)."""
import pytest

from core.browser_pool import (
    BrowserPoolError, ProviderTab, SharedBrowserPool, shared_browser_from_config,
)
from core.focus_guard import FocusViolation


class _Resp:
    def __init__(self, status=200, payload=None):
        self.status_code = status
        self._payload = payload or {}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"http {self.status_code}")

    def json(self):
        return self._payload


@pytest.fixture()
def pool():
    return SharedBrowserPool(cdp_url="http://127.0.0.1:9399", profile_dir=".runtime-dev/shared-profile")


def test_tab_for_creates_isolated_tabs_per_account(monkeypatch, pool):
    created = []

    def fake_put(url, params=None, timeout=None):
        target = f"T-{params['url']}-{len(created)}"
        created.append(target)
        return _Resp(200, {"id": target})

    monkeypatch.setattr("core.browser_pool.requests.put", fake_put)
    monkeypatch.setattr(SharedBrowserPool, "check_alive", lambda self: True)
    a = pool.tab_for("chatgpt-web", "acc-a", url="https://chatgpt.com/")
    b = pool.tab_for("chatgpt-web", "acc-b", url="https://chatgpt.com/")
    assert a.target_id != b.target_id
    assert pool.tab_for("chatgpt-web", "acc-a").target_id == a.target_id
    assert pool.resolve("chatgpt-web", "acc-b").target_id == b.target_id
    assert pool.resolve("chatgpt-web", "acc-unknown") is None


def test_bring_to_front_denied_for_background(pool):
    pool._tabs[("chatgpt-web", "default")] = ProviderTab(
        provider_id="chatgpt-web", account_id="default", target_id="T-1", url="about:blank")
    with pytest.raises(FocusViolation):
        pool.bring_to_front("chatgpt-web")
    with pool.focus_guard.user_initiated("open browser for login"):
        pool.bring_to_front("chatgpt-web")


def test_dead_browser_raises(pool, monkeypatch):
    monkeypatch.setattr(SharedBrowserPool, "check_alive", lambda self: False)
    with pytest.raises(BrowserPoolError):
        pool.tab_for("chatgpt-web")


def test_from_config_disabled_returns_none():
    assert shared_browser_from_config({}) is None
    assert shared_browser_from_config({"runtime_orchestration": {}}) is None
    cfg = {"runtime_orchestration": {"shared_browser": {
        "enabled": True, "cdp_url": "http://127.0.0.1:9399", "profile_dir": ".runtime-dev/shared"}}}
    pool = shared_browser_from_config(cfg)
    assert isinstance(pool, SharedBrowserPool)
    with pytest.raises(BrowserPoolError):
        shared_browser_from_config({"runtime_orchestration": {"shared_browser": {"enabled": True}}})
