"""ADR-002 pilot tests: chatgpt-web shared-pool binding (no live browser)."""
import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from adapters.chatgpt_web_provider import create_chatgpt_web_provider
from core.browser_pool import SharedBrowserPool


def _provider():
    return create_chatgpt_web_provider(cdp_url="http://127.0.0.1:9324")


def test_unbound_uses_own_cdp():
    p = _provider()
    assert p._shared_pool is None
    assert p._effective_cdp_url() == "http://127.0.0.1:9324"


def test_bind_unbind_switches_cdp():
    p = _provider()
    pool = SharedBrowserPool(cdp_url="http://127.0.0.1:9399", profile_dir="x")
    p.bind_shared_pool(pool)
    assert p._effective_cdp_url() == "http://127.0.0.1:9399"
    p.unbind_shared_pool()
    assert p._effective_cdp_url() == "http://127.0.0.1:9324"


def test_ensure_page_ensures_pool_tab():
    p = _provider()
    pool = MagicMock()
    pool.cdp_url = "http://127.0.0.1:9399"
    p.bind_shared_pool(pool)
    p._cleanup_connection = AsyncMock()
    p._connect = AsyncMock()
    sentinel = object()

    async def fake_rebind(require_composer=True):
        p._page = sentinel
        return {"composer_ready": True}

    p._rebind_chatgpt_page = fake_rebind
    asyncio.run(p._ensure_page())
    pool.tab_for.assert_called_once_with("chatgpt-web", "default", url=p._chatgpt_url)
    assert p._page is sentinel


def test_pool_failure_falls_back_to_legacy():
    p = _provider()
    pool = MagicMock()
    pool.cdp_url = "http://127.0.0.1:9399"
    pool.tab_for.side_effect = RuntimeError("pool down")
    p.bind_shared_pool(pool)
    p._cleanup_connection = AsyncMock()
    p._connect = AsyncMock()
    p._page = None

    async def fake_rebind(require_composer=True):
        return {"composer_ready": False}

    p._rebind_chatgpt_page = fake_rebind
    p._context = MagicMock()
    new_page = AsyncMock()
    new_page.goto = AsyncMock()
    p._context.new_page = AsyncMock(return_value=new_page)
    asyncio.run(p._ensure_page())  # must not raise
    assert pool.tab_for.called
