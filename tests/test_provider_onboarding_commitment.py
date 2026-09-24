import pytest


class _Locator:
    def __init__(self, page, kind, selector=''):
        self.page=page; self.kind=kind; self.selector=selector; self.first=self
    async def count(self): return 1
    async def is_visible(self): return True
    async def input_value(self): return self.page.composer_value
    async def get_attribute(self, name):
        return 'true' if self.kind=='composer' and name=='contenteditable' else None
    async def inner_text(self):
        if self.kind=='body': return self.page.body_text
        return self.page.composer_value
    async def fill(self, value): self.page.composer_value=value
    async def press_sequentially(self, value, delay=0):
        self.page.typed_values.append(value); self.page.composer_value += value
    async def press(self, key):
        self.page.pressed_keys.append(key)
        if key=='Backspace' and self.page.pressed_keys[-2:-1]==['Control+A']:
            self.page.composer_value=''
        if self.page.commit_on_enter and key=='Enter':
            self.page.composer_value=''
    async def bounding_box(self): return {'x':400,'y':400,'width':800,'height':80}
    async def click(self, **_kwargs):
        if self.kind=='submit':
            self.page.clicked_selector=self.selector
            if self.page.commit_on_click:
                self.page.composer_value=''
            if self.page.navigate_on_click:
                self.page.url='https://future.example/ai-agent'
                self.page.composer_value=''
        else:
            self.page.composer_clicks += 1


class _Session:
    async def send(self, _cmd): return {'targetInfo':{'targetId':'T1'}}
    async def detach(self): return None


class _Context:
    def __init__(self, page): self.pages=[page]
    async def new_cdp_session(self, _page): return _Session()


class _Browser:
    def __init__(self, page): self.contexts=[_Context(page)]


class _Chromium:
    def __init__(self, page): self.page=page
    async def connect_over_cdp(self, _url): return _Browser(self.page)


class _PW:
    def __init__(self, page): self.chromium=_Chromium(page)
    async def stop(self): return None


class _PWFactory:
    def __init__(self, page): self.page=page
    async def start(self): return _PW(self.page)


class _Page:
    url='https://future.example/'
    def __init__(self):
        self.composer_value=''; self.body_text=''; self.clicked_selector=None; self.commit_on_click=False; self.commit_on_enter=False; self.navigate_on_click=False; self.pressed_keys=[]; self.typed_values=[]; self.composer_clicks=0; self.eval_calls=0
    def locator(self, selector):
        if selector=='body': return _Locator(self,'body',selector)
        if selector=="div[contenteditable='true']": return _Locator(self,'composer',selector)
        return _Locator(self,'submit',selector)
    async def evaluate(self, _script):
        self.eval_calls += 1
        send={'selector':'#send','tag':'BUTTON','role':'','text':'','aria':'','title':'','rect':{'x':1180,'y':420,'w':32,'h':32}}
        wrong={'selector':'#wrong','tag':'BUTTON','role':'button','text':'','aria':'AI Images','title':'','rect':{'x':1170,'y':420,'w':40,'h':32},'disabled':None}
        if self.eval_calls==1: return [{**send,'disabled':True}]
        return [{**send,'disabled':None}, wrong]
    async def wait_for_timeout(self, _ms): return None
    def on(self, *_args): return None
    def remove_listener(self, *_args): return None


@pytest.mark.asyncio
async def test_recorded_enabled_transition_wins_and_uncommitted_click_is_retryable(monkeypatch):
    import core.provider_onboarding as po
    import core.visual_discovery as visual
    import playwright.async_api as pwa
    page=_Page()
    async def allowed(_page,_action): return {'allowed':True,'classification':{'state':'ready'}}
    async def final_state(_page): return {'body_tail':'','send_present':True,'send_enabled':True,'composer_present':True,'composer_enabled':True}
    monkeypatch.setattr(visual,'visual_action_gate',allowed)
    monkeypatch.setattr(po,'visible_page_state',final_state)
    monkeypatch.setattr(po,'SUBMIT_COMMITMENT_TIMEOUT_SECONDS',0.001)
    monkeypatch.setattr(pwa,'async_playwright',lambda:_PWFactory(page))
    record={'technical_candidate':{'workflow_state':'TECHNICAL_CANDIDATE_READY','target_id':'T1','composer_selector':"div[contenteditable='true']",'submit_candidates':[{'selector':'#send','text':'','aria':'','title':''}]}}
    out=await po.qualify_submit_candidate('http://127.0.0.1:9330',record,timeout_seconds=0.01)
    assert page.clicked_selector=='#send'
    assert out['status']=='E2_FAILED_BEFORE_COMMIT'
    assert out['submitted'] is False
    assert out['retry_allowed'] is True
    assert out['reason']=='submit_activation_not_committed'
    assert out['activation_strategy']=='click'
    assert page.composer_value==''


def test_commitment_request_filter_ignores_telemetry_and_quota():
    from core.provider_onboarding import meaningful_commitment_requests
    rows=[
        {"method":"POST","endpoint":"https://future.example/cdn-cgi/rum","resource_type":"xhr"},
        {"method":"GET","endpoint":"https://future.example/api/v2/user/quota","resource_type":"xhr"},
        {"method":"POST","endpoint":"https://analytics.google.com/g/collect","resource_type":"fetch"},
        {"method":"POST","endpoint":"https://future.example/api/chat","resource_type":"fetch"},
    ]
    out=meaningful_commitment_requests(rows)
    assert out==[rows[-1]]


@pytest.mark.asyncio
async def test_navigation_without_prompt_or_meaningful_request_is_precommit_transition(monkeypatch):
    import core.provider_onboarding as po
    import core.visual_discovery as visual
    import playwright.async_api as pwa
    page=_Page(); page.navigate_on_click=True
    async def allowed(_page,_action): return {"allowed":True,"classification":{"state":"ready"}}
    async def final_state(_page): return {"body_tail":"","send_present":False,"send_enabled":False,"composer_present":True,"composer_enabled":True}
    monkeypatch.setattr(visual,"visual_action_gate",allowed)
    monkeypatch.setattr(po,"visible_page_state",final_state)
    monkeypatch.setattr(po,"SUBMIT_COMMITMENT_TIMEOUT_SECONDS",0.001)
    monkeypatch.setattr(pwa,"async_playwright",lambda:_PWFactory(page))
    record={"technical_candidate":{"workflow_state":"TECHNICAL_CANDIDATE_READY","target_id":"T1","composer_selector":"div[contenteditable='true']","submit_candidates":[{"selector":"#send","text":"","aria":"","title":""}]}}
    out=await po.qualify_submit_candidate("http://127.0.0.1:9330",record,timeout_seconds=0.01)
    assert out["status"]=="E2_PRECOMMIT_TRANSITION"
    assert out["submitted"] is False
    assert out["retry_allowed"] is True
    assert out["reason"]=="precommit_page_transition"
    assert out["final_url"].endswith("/ai-agent")
