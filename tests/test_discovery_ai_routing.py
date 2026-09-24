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
    def __init__(self, provider_id, model, healthy=True, vision=False):
        self.provider_id=provider_id
        self._healthy=healthy
        self.capabilities=SimpleNamespace(supported_models=[model], vision=vision)
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


def test_ai_hypothesis_partition_keeps_click_out_of_auto_safe():
    from core.discovery_ai_service import _normalize_hypotheses
    rows=[
        {'target':'u1','meaning':'inspect me','confidence':'medium','evidence_refs':['control:u1'],'next_probe':'inspect','rationale':'safe'},
        {'target':'u2','meaning':'open menu','confidence':'high','evidence_refs':['control:u2'],'next_probe':'click','rationale':'needs action'},
    ]
    all_rows, safe, approval=_normalize_hypotheses(rows)
    assert len(all_rows)==2
    assert [x['target'] for x in safe]==['u1']
    assert [x['target'] for x in approval]==['u2']
    assert all(x['status']=='CANDIDATE' and x['evidence_level']=='E0' for x in all_rows)


def test_attach_verification_never_promotes_ai_semantics():
    from core.discovery_ai_verification import attach_verification_results
    finding={'finding':{'hypotheses':[{'target':'u1','meaning':'search','status':'CANDIDATE','evidence_level':'E0'}]}}
    out=attach_verification_results(finding,[{'target':'u1','probe':'inspect','status':'probe_completed','evidence_level':'E1'}])
    h=out['finding']['hypotheses'][0]
    assert h['status']=='VERIFICATION_OBSERVED'
    assert h['evidence_level']=='E0'
    assert h['semantic_promotion']=='blocked_pending_deterministic_classification'


def test_ai_service_requires_vision_capable_route_for_visual_evidence(tmp_path):
    image=tmp_path/'evidence.png'; image.write_bytes(b'not-an-image-but-present')
    target=_FakeProvider('target','target-model')
    text_only=_FakeProvider('text','text-model',vision=False)
    with pytest.raises(LookupError):
        asyncio.run(execute_ai_assistance(_FakeRegistry([target,text_only]),'target','run-v1',['inspect image'],{},user_approved=True,allow_target_provider=False,visual_evidence_paths=[str(image)],require_vision=True))


def test_ai_service_passes_visual_file_to_vision_provider(tmp_path):
    image=tmp_path/'evidence.png'; image.write_bytes(b'present')
    target=_FakeProvider('target','target-model')
    vision=_FakeProvider('vision','vision-model',vision=True)
    finding=asyncio.run(execute_ai_assistance(_FakeRegistry([target,vision]),'target','run-v2',['inspect image'],{},user_approved=True,allow_target_provider=False,visual_evidence_paths=[str(image)],require_vision=True))
    assert finding['provider']=='vision'
    assert finding['visual_evidence']=={'attached':True,'count':1,'vision_required':True}
    assert vision.calls[0].provider_options['file_paths']==[str(image.resolve())]
