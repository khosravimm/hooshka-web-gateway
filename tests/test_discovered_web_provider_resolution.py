import pytest
from adapters.discovered_web_provider import create_discovered_web_provider

class _Locator:
    first = None
    def __init__(self, selector): self.selector=selector; self.first=self
    async def count(self): return 1
    async def is_visible(self): return True

class _Composer:
    async def bounding_box(self): return {"x":400,"y":400,"width":800,"height":80}

class _Page:
    async def wait_for_timeout(self, _ms): return None
    async def evaluate(self, _script):
        return [
            {"selector":"#send","tag":"BUTTON","role":"","text":"","aria":"","title":"","disabled":False,"rect":{"x":1180,"y":420,"w":32,"h":32}},
            {"selector":"#wrong","tag":"BUTTON","role":"button","text":"","aria":"AI Images","title":"","disabled":False,"rect":{"x":1170,"y":420,"w":40,"h":32}},
        ]
    def locator(self, selector): return _Locator(selector)

@pytest.mark.asyncio
async def test_resolve_submit_prefers_recorded_enabled_transition():
    candidate={"transport":{"submit":{"last_verified_selector":"#send"}}}
    provider=create_discovered_web_provider("future-web",cdp_url="http://127.0.0.1:9330",home_url="https://future.example",adapter_candidate=candidate)
    before=[
        {"selector":"#send","tag":"BUTTON","role":"","text":"","aria":"","title":"","disabled":True,"rect":{"x":1180,"y":420,"w":32,"h":32}},
        {"selector":"#wrong","tag":"BUTTON","role":"button","text":"","aria":"AI Images","title":"","disabled":False,"rect":{"x":1170,"y":420,"w":40,"h":32}},
    ]
    loc, selector=await provider._resolve_submit(_Page(),_Composer(),before)
    assert selector=="#send"
    assert loc.selector=="#send"
