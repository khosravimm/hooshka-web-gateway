import asyncio
from types import SimpleNamespace

import pytest

import pytest

from core.discovery_ai_service import execute_ai_assistance
from core.discovery_ai_assist import AssistanceRequest, ai_assistance_allowed, normalize_ai_finding
from core.discovery_model_router import RouteCandidate, RouteRequest, select_candidate


def test_ai_assistance_requires_explicit_approval():
    req=AssistanceRequest('deepseek-web','r1','ambiguous control',['identify icon'],{'controls':[]})
    assert ai_assistance_allowed(req) == (False,'user_approval_required')
    req.user_approved=True
    assert ai_assistance_allowed(req)[0] is True


def test_ai_finding_stays_candidate_e0():
    item=normalize_ai_finding('model-a','provider-a',{'guess':'search toggle'})
    assert item['status']=='CANDIDATE'
    assert item['evidence_level']=='E0'
    assert item['validation_required'] is True


def test_router_respects_exact_provider_and_does_not_cross_route():
    candidates=[RouteCandidate('a','m1',healthy=False),RouteCandidate('b','m2')]
    with pytest.raises(LookupError):
        select_candidate(candidates,RouteRequest('discovery',exact_provider_id='a'))

def test_router_uses_health_capability_load_and_cooldown():
    candidates=[
        RouteCandidate('a','m1',capabilities=('vision',),inflight=3,weight=1),
        RouteCandidate('b','m2',capabilities=('vision',),inflight=1,weight=1),
        RouteCandidate('c','m3',capabilities=('vision',),inflight=0,cooldown_until='2999-01-01T00:00:00Z'),
    ]
    selected=select_candidate(candidates,RouteRequest('discovery',required_capabilities=('vision',)),'least_loaded')
    assert selected.provider_id=='b'


def test_router_rejects_unsupported_policy():
    with pytest.raises(ValueError):
        select_candidate([RouteCandidate('a','m')],RouteRequest('discovery'),'random_magic')


class _FakeProvider:
    def __init__(self, provider_id, model, healthy=True):
        self.provider_id=provider_id
        self._healthy=healthy
        self.capabilities=SimpleNamespace(supported_models=[model])
        self.config=SimpleNamespace(config={"default_model":model})
        self.calls=[]
    async def health_check(self):
        return self._healthy
    async def chat_completion(self, request):
        self.calls.append(request)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=f"analysis-by-{self.provider_id}"))])


class _FakeRegistry:
    def __init__(self, providers):
        self.providers={p.provider_id:p for p in providers}
    def list_providers(self, enabled_only=True):
        return list(self.providers.values())
    def get(self, provider_id):
        return self.providers.get(provider_id)


def test_ai_service_prefers_other_healthy_provider_for_target_analysis():
    target=_FakeProvider('deepseek-web','deepseek-model')
    helper=_FakeProvider('chatgpt-web','chatgpt-model')
    finding=asyncio.run(execute_ai_assistance(
        _FakeRegistry([target,helper]), 'deepseek-web','run-1',['what changed?'],{'baseline':{}},
        user_approved=True, allow_target_provider=False,
    ))
    assert finding['provider']=='chatgpt-web'
    assert finding['target_provider_avoided'] is True
    assert finding['status']=='CANDIDATE' and finding['evidence_level']=='E0'
    assert not target.calls and len(helper.calls)==1


def test_ai_service_fails_closed_when_only_target_exists_without_permission():
    target=_FakeProvider('deepseek-web','deepseek-model')
    with pytest.raises(LookupError):
        asyncio.run(execute_ai_assistance(
            _FakeRegistry([target]), 'deepseek-web','run-2',['ambiguous icon'],{'baseline':{}},
            user_approved=True, allow_target_provider=False,
        ))
    assert not target.calls


def test_ai_service_rejects_target_even_with_permission_when_transport_not_qualified():
    target=_FakeProvider('deepseek-web','deepseek-model')
    with pytest.raises(PermissionError, match='target_provider_transport_not_qualified'):
        asyncio.run(execute_ai_assistance(
            _FakeRegistry([target]), 'deepseek-web','run-3',['ambiguous control'],{'baseline':{}},
            user_approved=True, allow_target_provider=True,
        ))
    assert not target.calls


def test_ai_service_uses_target_only_after_transport_gate(monkeypatch):
    target=_FakeProvider('deepseek-web','deepseek-model')
    monkeypatch.setattr('core.discovery_ai_service.self_use_status', lambda provider: {'allowed':True,'reasons':[]})
    finding=asyncio.run(execute_ai_assistance(
        _FakeRegistry([target]), 'deepseek-web','run-4',['ambiguous control'],{'baseline':{}},
        user_approved=True, allow_target_provider=True,
    ))
    assert finding['provider']=='deepseek-web'
    assert finding['target_provider_avoided'] is False
    assert finding['self_use_transport_gate']['qualified'] is True
    assert len(target.calls)==1


def test_structured_ai_parser_accepts_fenced_json():
    from core.discovery_ai_service import _parse_structured_analysis
    text='''```json\n{"summary":"x","hypotheses":[{"target":"#a","meaning":"menu","confidence":"low","evidence_refs":[],"next_probe":"focus","rationale":"safe"}]}\n```'''
    out=_parse_structured_analysis(text)
    assert out['summary']=='x'
    assert out['hypotheses'][0]['next_probe']=='focus'


def test_structured_ai_parser_falls_back_without_promotion():
    from core.discovery_ai_service import _parse_structured_analysis
    out=_parse_structured_analysis('plain analysis')
    assert out['hypotheses']==[]
    assert out['summary']=='plain analysis'
