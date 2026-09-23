import desktop_runtime_agent as agent


def _item():
    return {"cdp_url":"http://127.0.0.1:9999","home_url":"https://chatgpt.com/","profile":"X:/profile","port":9999}


def test_shared_runtime_open_creates_missing_provider_tab(monkeypatch):
    item=_item(); calls=[]; states=iter([False, True, True])
    monkeypatch.setattr(agent,"cdp_ready",lambda _item: True)
    monkeypatch.setattr(agent,"provider_page_ready",lambda _item: next(states))
    monkeypatch.setattr(agent,"open_provider_tab",lambda _item: calls.append("open") or True)
    monkeypatch.setattr(agent,"visible_window_for_profile",lambda _profile:{"hwnd":1})
    monkeypatch.setattr(agent,"_foreground",lambda _window:calls.append("foreground"))
    assert agent.open_runtime_item(item) is True
    assert calls == ["open","foreground"]


def test_shared_runtime_open_reuses_existing_provider_tab(monkeypatch):
    item=_item(); calls=[]
    monkeypatch.setattr(agent,"cdp_ready",lambda _item: True)
    monkeypatch.setattr(agent,"provider_page_ready",lambda _item: True)
    monkeypatch.setattr(agent,"open_provider_tab",lambda _item:calls.append("open") or True)
    monkeypatch.setattr(agent,"visible_window_for_profile",lambda _profile:{"hwnd":1})
    monkeypatch.setattr(agent,"_foreground",lambda _window:calls.append("foreground"))
    assert agent.open_runtime_item(item) is True
    assert calls == ["foreground"]
