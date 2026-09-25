from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from core.discovery_model_router import RouteRequest, select_candidate
from core.discovery_ai_service import _route_candidates, _bounded_evidence, _parse_structured_analysis
from core.providers import ChatCompletionRequest

AUTO_SAFE_STEPS={
    'inspect_current_dom','inspect_visual_state','inspect_recorded_network',
    'correlate_response_surface','wait_and_reobserve'
}
APPROVAL_REQUIRED_STEPS={'click','resend_probe','login','accept_terms','captcha'}


def build_blocker_evidence(record: dict[str,Any]) -> dict[str,Any]:
    tc=record.get('technical_candidate') or {}
    obs=record.get('observation') or {}
    history=record.get('qualification_history') or []
    prior=[x for x in history if isinstance(x,dict) and x.get('status')=='E2_VERIFIED'][-3:]
    return {
        'candidate_id':record.get('candidate_id'),
        'workflow_state':tc.get('workflow_state'),
        'next_required':tc.get('next_required'),
        'user_action_required':tc.get('user_action_required'),
        'visual_classification':obs.get('classification') or {},
        'access_semantics':obs.get('access_semantics') or {},
        'submit_qualification':record.get('submit_qualification') or {},
        'qualification_diagnosis':record.get('qualification_diagnosis') or {},
        'prior_e2_verified_attempts':prior,
    }

def _normalize_steps(items:list[Any]) -> tuple[list[dict[str,Any]],list[dict[str,Any]]]:
    safe=[]; gated=[]
    for raw in items:
        if not isinstance(raw,dict):
            continue
        kind=str(raw.get('kind') or '').strip().lower()
        if kind not in AUTO_SAFE_STEPS|APPROVAL_REQUIRED_STEPS:
            continue
        item={
            'kind':kind,
            'rationale':str(raw.get('rationale') or '').strip(),
            'evidence_refs':[str(x) for x in (raw.get('evidence_refs') or [])][:12],
            'confidence':str(raw.get('confidence') or 'low').lower(),
        }
        if item['confidence'] not in {'low','medium','high'}:
            item['confidence']='low'
        (safe if kind in AUTO_SAFE_STEPS else gated).append(item)
    return safe,gated


async def execute_ai_blocker_diagnosis(registry,target_provider_id:str,record:dict[str,Any],*,routing_policy:str='least_loaded') -> dict[str,Any]:
    evidence=build_blocker_evidence(record)
    candidates=await _route_candidates(registry)
    selected=select_candidate(candidates,RouteRequest(
        purpose='discovery_ai_blocker_diagnosis',
        required_capabilities=('chat',),
        avoid_provider_id=target_provider_id,
    ),routing_policy)
    provider=registry.get(selected.provider_id)
    if provider is None:
        raise LookupError('selected provider disappeared')
    prompt=(
        'Analyze this Web Chat Explorer blocker from recorded evidence only. '
        'Do not invent observations and do not claim a blocker is solved without deterministic verification. '
        'Return strict JSON with keys summary, blocker_kind, likely_causes, next_steps, terminal_recommendation. '
        'Each next_steps item: kind, rationale, evidence_refs, confidence. Allowed kind values: '
        + ','.join(sorted(AUTO_SAFE_STEPS|APPROVAL_REQUIRED_STEPS)) + '. '
        'Prefer read-only steps. resend_probe, click, login, accept_terms and captcha always require human approval. '
        'terminal_recommendation must be one of continue_readonly, human_gate, new_probe_requires_approval, cannot_resolve.\n\n'
        f'Target provider: {target_provider_id}\nEvidence: {_bounded_evidence(evidence,16000)}'
    )
    response=await provider.chat_completion(ChatCompletionRequest(
        model=selected.model,
        messages=[
            {'role':'system','content':'You are a cautious browser-discovery failure analyst. Evidence first; no unsafe bypasses.'},
            {'role':'user','content':prompt},
        ],
        stream=False,max_tokens=1400,
    ))
    text=response.choices[0].message.content if response.choices else ''
    structured=_parse_structured_analysis(text)
    safe,gated=_normalize_steps(structured.get('next_steps') if isinstance(structured.get('next_steps'),list) else [])
    recommendation=str(structured.get('terminal_recommendation') or 'cannot_resolve').strip().lower()
    if recommendation not in {'continue_readonly','human_gate','new_probe_requires_approval','cannot_resolve'}:
        recommendation='cannot_resolve'
    return {
        'source':'ai_blocker_diagnosis',
        'status':'CANDIDATE',
        'evidence_level':'E0',
        'validation_required':True,
        'provider':selected.provider_id,
        'model':selected.model,
        'target_provider_avoided':selected.provider_id != target_provider_id,
        'summary':str(structured.get('summary') or text[:2000]).strip(),
        'blocker_kind':str(structured.get('blocker_kind') or 'unknown').strip(),
        'likely_causes':structured.get('likely_causes') if isinstance(structured.get('likely_causes'),list) else [],
        'auto_safe_steps':safe,
        'approval_required_steps':gated,
        'terminal_recommendation':recommendation,
        'raw_structured':structured,
    }



def verify_ai_blocker_plan(cdp_url:str,record:dict[str,Any],diagnosis:dict[str,Any]) -> dict[str,Any]:
    import time
    from core.provider_onboarding import diagnose_committed_qualification_sync
    safe={str(x.get('kind') or '') for x in (diagnosis.get('auto_safe_steps') or []) if isinstance(x,dict)}
    result={'status':'AI_PLAN_VERIFIED','evidence_level':'E1','executed':[],'recovered':False}
    current=record.get('submit_qualification') or {}
    responses=list(current.get('network_responses') or [])
    if 'inspect_recorded_network' in safe:
        result['executed'].append('inspect_recorded_network')
        result['network_response_count']=len(responses)
        result['transport_marker_found']=bool(current.get('transport_marker_found')) or any(bool(x.get('expected_marker_found')) for x in responses)
        result['transport_http_errors']=[x for x in responses if int(x.get('status') or 0)>=400][:10]
    if 'wait_and_reobserve' in safe:
        time.sleep(1.0); result['executed'].append('wait_and_reobserve')
    if safe & {'inspect_current_dom','inspect_visual_state','correlate_response_surface','wait_and_reobserve'}:
        diag=diagnose_committed_qualification_sync(cdp_url,record)
        result['executed'].append('committed_qualification_recheck')
        result['deterministic_recheck']=diag
        if diag.get('status')=='E2_RECOVERED':
            result['status']='E2_RECOVERED'; result['recovered']=True; result['qualification']=diag.get('qualification') or {}; return result
    prior=[x for x in (record.get('qualification_history') or []) if isinstance(x,dict) and x.get('status')=='E2_VERIFIED']
    result['prior_e2_verified_count']=len(prior)
    result['prior_response_strategies']=list(dict.fromkeys(str((x.get('response_surface') or {}).get('strategy') or '') for x in prior if (x.get('response_surface') or {}).get('strategy')))[-5:]
    if result.get('transport_marker_found'):
        result['status']='E2_TRANSPORT_MARKER_VERIFIED'; result['next_required']='response_surface_mapping_without_resend'; return result
    gated={str(x.get('kind') or '') for x in (diagnosis.get('approval_required_steps') or []) if isinstance(x,dict)}
    attempts=int(record.get('auto_instrumented_probe_attempts') or 0)
    if attempts >= 1:
        result['status']='FINAL_INCONCLUSIVE'; result['next_required']='stop_without_enable'; result['reason']='instrumented_probe_exhausted_without_verifiable_response'; return result
    if 'resend_probe' in gated:
        result['status']='AUTO_PROBE_REQUIRED'; result['next_required']='run_new_instrumented_probe'; result['reason']='technical_evidence_requires_new_probe'; return result
    # Technical sufficiency is an Explorer decision, not a user decision. Once all read-only
    # evidence is exhausted, request one bounded instrumented synthetic probe automatically.
    result['status']='AUTO_PROBE_REQUIRED'; result['next_required']='run_new_instrumented_probe'; result['reason']='read_only_evidence_exhausted'
    return result
