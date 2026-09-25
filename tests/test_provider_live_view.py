import pytest
import core.provider_live_view as live

class _Page:
    def __init__(self, url, tid):
        self.url=url; self.tid=tid

class _Context:
    def __init__(self, pages): self.pages=pages

@pytest.mark.asyncio
async def test_find_page_with_target_id_never_falls_back_to_same_origin(monkeypatch):
    pages=[_Page('https://notegpt.io/a','A'),_Page('https://notegpt.io/b','B')]
    async def fake_target_id(_context,page): return page.tid
    monkeypatch.setattr(live,'_target_id',fake_target_id)
    found=await live._find_page(_Context(pages),target_id='MISSING',url='https://notegpt.io/')
    assert found is None

@pytest.mark.asyncio
async def test_find_owned_page_reuses_owned_same_origin(monkeypatch):
    pages=[_Page('https://notegpt.io/ai-agent','OWNED')]
    async def fake_target_id(_context,page): return page.tid
    monkeypatch.setattr(live,'_target_id',fake_target_id)
    live._OWNED_TARGETS.clear(); live._OWNED_TARGETS.add(('cdp://x','OWNED'))
    page,tid=await live._find_owned_page(_Context(pages),'cdp://x','https://notegpt.io/')
    assert page is pages[0] and tid=='OWNED'
