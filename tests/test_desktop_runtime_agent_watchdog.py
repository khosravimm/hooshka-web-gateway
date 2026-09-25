import desktop_runtime_agent as agent


def test_ensure_enabled_recovers_dead_enabled_runtime(monkeypatch):
    item={"id":"deepseek-web","enabled":True,"cdp_url":"http://127.0.0.1:9330","profile":"X:/profile","port":9330,"home_url":"https://chat.deepseek.com/"}
    monkeypatch.setattr(agent,"load_runtime_inventory",lambda:[item])
    monkeypatch.setattr(agent,"cdp_ready",lambda _item:False)
    calls=[]
    monkeypatch.setattr(agent,"start_runtime_item",lambda _item:calls.append(_item["id"]) or True)
    result=agent.ensure_enabled()
    assert result == {"checked":1,"recovered":["deepseek-web"],"errors":[]}
    assert calls == ["deepseek-web"]


def test_ensure_enabled_ignores_disabled_and_ready_runtimes(monkeypatch):
    rows=[
        {"id":"off","enabled":False},
        {"id":"ready","enabled":True},
    ]
    monkeypatch.setattr(agent,"load_runtime_inventory",lambda:rows)
    monkeypatch.setattr(agent,"cdp_ready",lambda item:item["id"]=="ready")
    monkeypatch.setattr(agent,"start_runtime_item",lambda _item: (_ for _ in ()).throw(AssertionError("must not start")))
    result=agent.ensure_enabled()
    assert result == {"checked":1,"recovered":[],"errors":[]}


def test_watchdog_once_updates_observable_state(monkeypatch):
    monkeypatch.setattr(agent,"ensure_enabled",lambda:{"checked":1,"recovered":["deepseek-web"],"errors":[]})
    before_checks=agent._WATCHDOG_STATE["checks"]
    before_recoveries=agent._WATCHDOG_STATE["recoveries"]
    result=agent._watchdog_once()
    assert result["recovered"] == ["deepseek-web"]
    assert agent._WATCHDOG_STATE["checks"] == before_checks + 1
    assert agent._WATCHDOG_STATE["recoveries"] == before_recoveries + 1
    assert agent._WATCHDOG_STATE["last_check_at"].endswith("Z")
