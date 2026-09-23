import pytest

from core.visual_discovery import visible_page_state, wait_for_upload_settled


class FakePage:
    def __init__(self, states):
        self.states=list(states)
        self.index=0
        self.screens=[]

    async def evaluate(self, _script):
        state=self.states[min(self.index, len(self.states)-1)]
        self.index += 1
        return state

    async def screenshot(self, path, full_page=False):
        self.screens.append((path, full_page))

    async def wait_for_timeout(self, _ms):
        return None


@pytest.mark.asyncio
async def test_visible_state_uses_accessible_attachment_label_when_filename_is_truncated():
    page=FakePage([{"url":"https://x","title":"x","viewport":{},"body":"Uploading\nhwg_file...",
                    "controls":[{"label":"Remove hwg_file_long.txt","testid":"","text":"","disabled":False,"aria_disabled":None},
                                {"label":"Send","testid":"","text":"","disabled":True,"aria_disabled":"true"}]}])
    state=await visible_page_state(page,"hwg_file_long.txt")
    assert state["attachment_visible"] is True
    assert state["upload_busy"] is True
    assert state["send_enabled"] is False

@pytest.mark.asyncio
async def test_wait_for_upload_settled_requires_busy_state_to_clear(tmp_path):
    states=[
        {"url":"https://x","title":"x","viewport":{},"body":"Uploading\nhwg.txt","controls":[{"label":"Remove hwg.txt","testid":"","text":"","disabled":False,"aria_disabled":None}]},
        {"url":"https://x","title":"x","viewport":{},"body":"Uploading\nhwg.txt","controls":[{"label":"Remove hwg.txt","testid":"","text":"","disabled":False,"aria_disabled":None}]},
        {"url":"https://x","title":"x","viewport":{},"body":"hwg.txt","controls":[{"label":"Remove hwg.txt","testid":"","text":"","disabled":False,"aria_disabled":None},{"label":"Send","testid":"","text":"","disabled":False,"aria_disabled":"false"}]},
    ]
    page=FakePage(states)
    result=await wait_for_upload_settled(page,"provider","hwg.txt",timeout_seconds=1,settle_seconds=0.01)
    assert result["ready"] is True
    assert result["final"]["upload_busy"] is False
    assert result["final"]["attachment_visible"] is True


@pytest.mark.asyncio
async def test_visible_state_prefers_real_composer_send_control():
    page=FakePage([{"url":"https://x","title":"x","viewport":{},"body":"",
                    "controls":[
                        {"id":"","label":"Send feedback","testid":"","text":"Send","disabled":False,"aria_disabled":None},
                        {"id":"send-message-button","label":"Send Message","testid":"","text":"","disabled":True,"aria_disabled":"true"},
                    ]}])
    state=await visible_page_state(page)
    assert state["send_present"] is True
    assert state["send_enabled"] is False
    assert state["send_controls"][0]["id"] == "send-message-button"
