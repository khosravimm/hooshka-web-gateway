from pathlib import Path
import main
from core.mcp import mcp_session_manager

ROOT=Path(__file__).resolve().parent.parent

def _client():
    app=main.create_app(str(ROOT/'config.yaml'))
    app.config['TESTING']=True
    return app.test_client()

def test_cancel_requires_provider_or_known_conversation():
    r=_client().post('/v1/chat/cancel',json={})
    assert r.status_code==400
    assert r.get_json()['error']['code']=='cancel_target_required'

def test_cancel_resolves_provider_from_conversation(monkeypatch):
    c=_client(); provider=main.provider_registry.get('deepseek-web')
    mcp_session_manager.get_or_create_session('cancel-test-conv',provider)
    async def fake(reason): return {'supported':True,'cancelled':True,'method':'test_hook','reason':reason}
    monkeypatch.setattr(provider,'cancel_active_generation',fake)
    r=c.post('/v1/chat/cancel',json={'conversation_id':'cancel-test-conv','reason':'sdk_stop'})
    body=r.get_json()
    assert r.status_code==200
    assert body['provider']=='deepseek-web' and body['cancelled'] is True
    assert body['method']=='test_hook'

def test_cancel_rejects_provider_conversation_mismatch(monkeypatch):
    c=_client(); provider=main.provider_registry.get('deepseek-web')
    mcp_session_manager.get_or_create_session('cancel-mismatch-conv',provider)
    r=c.post('/v1/chat/cancel',json={'conversation_id':'cancel-mismatch-conv','provider':'chatgpt-web'})
    assert r.status_code==409
    assert r.get_json()['error']['code']=='conversation_provider_mismatch'