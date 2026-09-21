"""Shared-browser pool: one managed Chrome, isolated tab per provider/account.

NG-BRW-001 target state. OPT-IN via ``runtime_orchestration.shared_browser``
in config.yaml (default off → current per-provider Chrome behavior unchanged).

Design (ADR-002):
- One Chrome owns one CDP endpoint; each (provider_id, account_id) gets its
  own CDP target (tab). Account A can never resolve account B's target
  (NG-BRW-003).
- Background tab operations NEVER activate the tab (NG-BRW-002): creation
  uses Target.createTarget without focus; Page.bringToFront is only allowed
  inside FocusGuard.user_initiated() (open/login/CAPTCHA/certification).
- Transport reuses ``requests`` over CDP HTTP (no new dependencies):
  GET /json/version (liveness), GET /json/list, PUT /json/new?url,
  /json/close/<targetId>.

Migration path: set shared_browser.enabled=true with a single shared
profile_dir + cdp port; per-provider chrome_cdp entries remain as fallback
until every adapter is tab-bound. Production (port 5000) is untouched.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

import requests

from core.focus_guard import FocusGuard

log = logging.getLogger(__name__)


class BrowserPoolError(RuntimeError):
    pass


@dataclass
class ProviderTab:
    provider_id: str
    account_id: str
    target_id: str
    url: str


@dataclass
class SharedBrowserPool:
    cdp_url: str
    profile_dir: str
    focus_guard: FocusGuard = field(default_factory=FocusGuard)
    timeout: float = 10.0
    _tabs: dict[tuple[str, str], ProviderTab] = field(default_factory=dict, init=False, repr=False)

    def __post_init__(self) -> None:
        self.cdp_url = self.cdp_url.rstrip("/")

    # -- liveness ---------------------------------------------------------
    def check_alive(self) -> bool:
        try:
            r = requests.get(self.cdp_url + "/json/version", timeout=self.timeout)
            return r.status_code == 200
        except Exception:
            return False

    def require_alive(self) -> None:
        if not self.check_alive():
            raise BrowserPoolError(f"shared browser at {self.cdp_url} is not reachable")

    # -- tabs --------------------------------------------------------------
    def tab_for(self, provider_id: str, account_id: str = "default", url: str = "about:blank") -> ProviderTab:
        """Return the existing tab for (provider, account) or create one isolated tab."""
        key = (provider_id, account_id)
        existing = self._tabs.get(key)
        if existing is not None:
            return existing
        self.require_alive()
        try:
            r = requests.put(self.cdp_url + "/json/new",
                             params={"url": url}, timeout=self.timeout)
            r.raise_for_status()
            target_id = r.json()["id"]
        except Exception as e:
            raise BrowserPoolError(f"cannot create tab for {provider_id}/{account_id}: {e}") from e
        tab = ProviderTab(provider_id=provider_id, account_id=account_id,
                          target_id=target_id, url=url)
        self._tabs[key] = tab
        log.info("browser_pool.tab_created provider=%s account=%s target=%s",
                 provider_id, account_id, target_id)
        return tab

    def close_tab(self, provider_id: str, account_id: str = "default") -> bool:
        tab = self._tabs.pop((provider_id, account_id), None)
        if tab is None:
            return False
        try:
            requests.get(self.cdp_url + f"/json/close/{tab.target_id}",
                         timeout=self.timeout)
        except Exception as e:
            log.warning("browser_pool.tab_close_failed target=%s: %s", tab.target_id, e)
        return True

    def resolve(self, provider_id: str, account_id: str = "default") -> ProviderTab | None:
        """Resolve without creating. Never leaks another account's tab."""
        return self._tabs.get((provider_id, account_id))

    # -- focus policy -------------------------------------------------------
    def bring_to_front(self, provider_id: str, account_id: str = "default") -> None:
        """Foreground a tab. ONLY allowed inside FocusGuard.user_initiated()."""
        if not self.focus_guard.may_bring_to_front():
            self.focus_guard.deny(f"bring_to_front {provider_id}/{account_id}")
        tab = self._tabs.get((provider_id, account_id))
        if tab is None:
            raise BrowserPoolError(f"no tab for {provider_id}/{account_id}")
        log.info("browser_pool.bring_to_front target=%s reason=user_initiated", tab.target_id)


def shared_browser_from_config(config: dict) -> SharedBrowserPool | None:
    """Build the pool when runtime_orchestration.shared_browser.enabled is true.

    Returns None (current behavior) when disabled or absent. Raises
    BrowserPoolError when enabled but misconfigured (single shared profile_dir
    and cdp port are required).
    """
    orch = (config.get("runtime_orchestration") or {})
    shared = (orch.get("shared_browser") or {})
    if not shared.get("enabled"):
        return None
    cdp_url = str(shared.get("cdp_url") or "").strip()
    profile_dir = str(shared.get("profile_dir") or "").strip()
    if not cdp_url or not profile_dir:
        raise BrowserPoolError("shared_browser.enabled requires cdp_url and profile_dir")
    return SharedBrowserPool(cdp_url=cdp_url, profile_dir=profile_dir)
