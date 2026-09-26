import control_panel


def test_browser_runtime_groups_collapse_shared_runtime(monkeypatch):
    inv={
      'chatgpt-web':{'id':'chatgpt-web','label':'ChatGPT','cdp_url':'http://127.0.0.1:9330','port':9330,'profile':'P','home_url':'https://chatgpt.com/','enabled':True},
      'zai-web':{'id':'zai-web','label':'Z.ai','cdp_url':'http://127.0.0.1:9330','port':9330,'profile':'P','home_url':'https://chat.z.ai/','enabled':True},
      'qwen-web':{'id':'qwen-web','label':'Qwen','cdp_url':'http://127.0.0.1:9325','port':9325,'profile':'Q','home_url':'https://chat.qwen.ai/','enabled':False},
    }
    monkeypatch.setattr(control_panel,'inventory_by_id',lambda path:inv)
    monkeypatch.setattr(control_panel,'load_ng_inventory',lambda path:{'account_instances':[]})
    monkeypatch.setattr(control_panel,'_check_cdp',lambda url:{'ready':True,'status':'ready'})
    groups=control_panel._browser_runtime_groups()
    assert len(groups)==2
    shared=next(g for g in groups if g['port']==9330)
    assert shared['shared'] is True and shared['provider_count']==2
    assert {p['id'] for p in shared['providers']}=={'chatgpt-web','zai-web'}


def test_runtime_ui_uses_browser_groups_not_provider_cards():
    js=open('control_panel_ui/panel.js',encoding='utf-8-sig').read()
    assert "api('/browser-runtimes')" in js
    assert 'provider_count' in js
    assert 'representative_provider' in js
