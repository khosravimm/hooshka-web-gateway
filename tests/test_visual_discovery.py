import pytest

from core.visual_discovery import visible_page_state, wait_for_upload_settled, visible_interaction_map


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


@pytest.mark.asyncio
async def test_visible_interaction_map_contract():
    expected={"viewport":{"width":1200,"height":800},"scroll":{"width":1200,"height":1600,"x":0,"y":0},"horizontal_overflow":False,"controls":[{"id":"send","disabled":True}],"headings":[{"text":"Chat"}],"clipped":[],"visible_text":"Chat"}
    page=FakePage([expected])
    result=await visible_interaction_map(page)
    assert result["horizontal_overflow"] is False
    assert result["controls"][0]["id"] == "send"
    assert result["headings"][0]["text"] == "Chat"


@pytest.mark.asyncio
async def test_visible_state_recognizes_image_preview_alt_as_attachment():
    page=FakePage([{"url":"https://x","title":"x","viewport":{},"body":"","controls":[],"composers":[],
                    "media":[{"tag":"IMG","alt":"visual-proof.png","label":"","title":"","src":"blob:https://x/1","rect":{"x":10,"y":10,"w":64,"h":64}}]}])
    state=await visible_page_state(page,"visual-proof.png")
    assert state["attachment_visible"] is True
    assert state["media_previews"][0]["alt"] == "visual-proof.png"


@pytest.mark.asyncio
async def test_visual_action_gate_blocks_quota_before_media_action():
    from core.visual_discovery import visual_action_gate
    page=FakePage([{"url":"https://x","title":"x","viewport":{},"body":"Processing limit reached. Try after quota resets.","controls":[],"composers":[]}])
    result=await visual_action_gate(page,"media_qualification")
    assert result["allowed"] is False
    assert result["classification"]["state"] == "quota_limited"
    assert result["reason"] == "blocked_by_provider_state"

@pytest.mark.asyncio
async def test_visual_action_gate_allows_clear_media_page():
    from core.visual_discovery import visual_action_gate
    page=FakePage([{"url":"https://x","title":"x","viewport":{},"body":"Chat ready","controls":[],"composers":[{"disabled":False}]}])
    result=await visual_action_gate(page,"media_qualification")
    assert result["allowed"] is True
    assert result["reason"] == "visual_preflight_clear"


@pytest.mark.asyncio
async def test_visual_action_gate_scopes_file_quota_to_media_only():
    from core.visual_discovery import visual_action_gate
    state={"url":"https://x","title":"x","viewport":{},"body":"File processing limit reached for the free plan.","controls":[],"composers":[]}
    media=await visual_action_gate(FakePage([state]),"media_qualification")
    send=await visual_action_gate(FakePage([state]),"send")
    assert media["allowed"] is False
    assert media["classification"]["state"] == "quota_limited"
    assert media["classification"]["scope"] == "media"
    assert send["allowed"] is True

@pytest.mark.asyncio
async def test_visual_action_gate_blocks_general_quota_for_send():
    from core.visual_discovery import visual_action_gate
    state={"url":"https://x","title":"x","viewport":{},"body":"Usage limit reached. Try again later.","controls":[],"composers":[]}
    send=await visual_action_gate(FakePage([state]),"send")
    assert send["allowed"] is False
    assert send["classification"]["scope"] == "general"


@pytest.mark.asyncio
async def test_visual_action_gate_blocks_login_required():
    from core.visual_discovery import visual_action_gate
    state={"url":"https://x","title":"x","viewport":{},"body":"Sign in to continue","controls":[],"composers":[]}
    result=await visual_action_gate(FakePage([state]),"media_qualification")
    assert result["allowed"] is False
    assert result["classification"]["state"] == "login_required"


@pytest.mark.asyncio
async def test_visual_action_gate_blocks_challenge():
    from core.visual_discovery import visual_action_gate
    state={"url":"https://x","title":"x","viewport":{},"body":"Verify you are human to continue","controls":[],"composers":[]}
    result=await visual_action_gate(FakePage([state]),"media_qualification")
    assert result["allowed"] is False
    assert result["classification"]["state"] == "challenge"


@pytest.mark.asyncio
async def test_visual_action_gate_blocks_persian_media_quota():
    from core.visual_discovery import visual_action_gate
    state={"url":"https://x","title":"x","viewport":{},"body":"محدودیت پردازش فایل در بسته‌ی رایگان. پس از آزادسازی سهمیه، پردازش فایل‌های جدید دوباره در دسترس خواهد بود.","controls":[],"composers":[]}
    result=await visual_action_gate(FakePage([state]),"media_qualification")
    assert result["allowed"] is False
    assert result["classification"]["state"] == "quota_limited"
    assert result["classification"]["scope"] == "media"


@pytest.mark.asyncio
async def test_visual_action_gate_blocks_general_quota_for_probe():
    from core.visual_discovery import visual_action_gate
    state={"url":"https://x","title":"x","viewport":{},"body":"Usage limit reached. Try again later.","controls":[],"composers":[]}
    result=await visual_action_gate(FakePage([state]),"probe")
    assert result["allowed"] is False
    assert result["classification"]["state"] == "quota_limited"


@pytest.mark.asyncio
async def test_visual_action_gate_blocks_login_for_provider_interaction():
    from core.visual_discovery import visual_action_gate
    state={"url":"https://x","title":"x","viewport":{},"body":"Sign in to continue","controls":[],"composers":[]}
    result=await visual_action_gate(FakePage([state]),"provider_interaction")
    assert result["allowed"] is False
    assert result["classification"]["state"] == "login_required"


@pytest.mark.asyncio
async def test_visual_action_gate_blocks_challenge_for_certification_probe():
    from core.visual_discovery import visual_action_gate
    state={"url":"https://x","title":"x","viewport":{},"body":"CAPTCHA security check","controls":[],"composers":[]}
    result=await visual_action_gate(FakePage([state]),"certification_probe")
    assert result["allowed"] is False
    assert result["classification"]["state"] == "challenge"

@pytest.mark.asyncio
async def test_visual_action_gate_blocks_auth_ambiguous_certification():
    from core.visual_discovery import visual_action_gate
    state={"url":"https://x","title":"x","viewport":{},"body":"","controls":[{"label":"","testid":"","text":"Sign In","disabled":False,"aria_disabled":None}],"composers":[{"disabled":False}]}
    result=await visual_action_gate(FakePage([state]),"certification_probe")
    assert result["allowed"] is False
    assert result["classification"]["state"]=="auth_ambiguous"


@pytest.mark.asyncio
async def test_visual_action_gate_fails_closed_while_loading():
    from core.visual_discovery import visual_action_gate
    state={"url":"https://x","title":"x","viewport":{},"body":"Loading","controls":[],"composers":[],"loading":[{"tag":"DIV","text":"Loading","cls":"loading"}]}
    result=await visual_action_gate(FakePage([state]),"send")
    assert result["allowed"] is False
    assert result["classification"]["state"]=="loading"
    assert result["reason"]=="blocked_by_visual_readiness"


@pytest.mark.asyncio
async def test_visual_action_gate_fails_closed_when_view_state_unknown():
    from core.visual_discovery import visual_action_gate
    state={"url":"https://x","title":"x","viewport":{},"body":"Welcome","controls":[],"composers":[]}
    result=await visual_action_gate(FakePage([state]),"provider_interaction")
    assert result["allowed"] is False
    assert result["classification"]["state"]=="unknown"
