import asyncio
from dataclasses import replace

from core.functional_readiness import run_functional_probe, save_readiness, load_readiness, invalidate_readiness
from core.providers import Provider, ProviderConfig, ProviderType, ProviderCapabilities, ModelInfo, ChatCompletionResponse, Choice, Message, Usage


class DummyProvider(Provider):
    def __init__(self, *, echo=True):
        super().__init__(ProviderConfig(
            provider_id="dummy-web", provider_type=ProviderType.CUSTOM,
            capabilities=ProviderCapabilities(supported_models=["dummy-web"], search=True, reasoning=True),
            config={"feature_defaults":{"thinking":False,"search":False},"feature_controls":{"thinking":True,"search":True}},
        ))
        self.echo=echo

    async def health_check(self): return True
    async def list_models(self): return [ModelInfo(id="dummy-web", owned_by="dummy", provider="dummy-web")]
    async def chat_completion_stream(self, request, session=None):
        if False: yield None
    async def close(self): return None

    async def chat_completion(self, request, session=None):
        marker=request.messages[-1]["content"].split(": ")[-1]
        text=marker if self.echo else "wrong"
        return ChatCompletionResponse(id="x",created=1,model=request.model,
            choices=[Choice(index=0,message=Message(role="assistant",content=text),finish_reason="stop")],
            usage=Usage())


def test_ready_requires_functional_roundtrip():
    p=DummyProvider(echo=True)
    r=asyncio.run(run_functional_probe(p,account_id="a",runtime_ready=True,access_state="AUTHENTICATED",ttl_seconds=60))
    assert r["state"]=="READY" and r["ready"] is True
    assert [x["stage"] for x in r["stages"]]==["runtime_cdp","access_auth","model_state","feature_state","functional_probe"]


def test_wrong_roundtrip_is_not_ready():
    p=DummyProvider(echo=False)
    r=asyncio.run(run_functional_probe(p,account_id="a",runtime_ready=True,access_state="AUTHENTICATED"))
    assert r["state"]=="FUNCTIONAL_PROBE_FAILED"
    assert r["ready"] is False


def test_blocked_access_short_circuits_before_probe():
    p=DummyProvider(echo=True)
    r=asyncio.run(run_functional_probe(p,account_id="a",runtime_ready=True,access_state="BLOCKED"))
    assert r["state"]=="BLOCKED"
    assert r["ready"] is False
    assert [x["stage"] for x in r["stages"]]==["runtime_cdp","access_auth"]


def test_readiness_cache_and_invalidation(tmp_path):
    p=DummyProvider(echo=True)
    r=asyncio.run(run_functional_probe(p,account_id="a",runtime_ready=True,access_state="AUTHENTICATED",ttl_seconds=60))
    save_readiness(r,tmp_path)
    current=load_readiness("dummy-web",tmp_path)
    assert current["current"] is True and current["ready"] is True
    invalid=invalidate_readiness("dummy-web","logout",tmp_path)
    assert invalid["state"]=="INVALIDATED"
    assert load_readiness("dummy-web",tmp_path)["current"] is False


def test_control_plane_exposes_functional_readiness_routes_and_ui():
    from pathlib import Path
    root=Path(__file__).resolve().parents[1]
    panel=(root/'control_panel.py').read_text(encoding='utf-8-sig')
    ui=(root/'control_panel_ui/panel.js').read_text(encoding='utf-8-sig')
    assert "/api/readiness" in panel
    assert "/api/providers/<provider_id>/readiness/probe" in panel
    assert "run_functional_probe" in panel
    assert "HwgReadinessProbe" in ui
    assert "READY عملکردی" in ui
    assert "execution_authority:'automated_validation'" in ui


def test_logout_and_non_authenticated_session_invalidate_readiness():
    from pathlib import Path
    root=Path(__file__).resolve().parents[1]
    panel=(root/'control_panel.py').read_text(encoding='utf-8-sig')
    assert 'invalidate_readiness(provider_id, "explicit_logout")' in panel
    assert 'invalidate_readiness(provider_id, f"session:{lifecycle.get(\'access_state\')}")' in panel
