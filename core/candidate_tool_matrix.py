from __future__ import annotations

import asyncio, json, uuid
from typing import Any

from adapters.discovered_web_provider import create_discovered_web_provider
from core.provider_onboarding import generate_adapter_candidate
from core.providers import ChatCompletionRequest
from core.tool_protocol import parse_tool_envelope
from core.candidate_tool_qualification import _target_page


def _args(call: dict[str, Any]) -> dict[str, Any]:
    raw=((call or {}).get('function') or {}).get('arguments') or '{}'
    if isinstance(raw,dict): return raw
    try:
        value=json.loads(raw); return value if isinstance(value,dict) else {}
    except Exception: return {}


def _call_name(call: dict[str, Any]) -> str:
    return str(((call or {}).get('function') or {}).get('name') or '')


async def _ask(provider, prompt: str, timeout_seconds: float=32.0) -> tuple[str,list[dict],bool]:
    response=await asyncio.wait_for(
        provider.chat_completion(ChatCompletionRequest(
            model=provider.provider_id,
            messages=[{'role':'user','content':prompt}],
            stream=False,
            max_tokens=256,
        )),
        timeout_seconds,
    )
    raw=str(response.choices[0].message.content or '')
    content,calls,valid=parse_tool_envelope(raw)
    return raw,list(calls or []),bool(valid)

async def qualify_tool_matrix(cdp_url: str, record: dict[str, Any]) -> dict[str, Any]:
    adapter=generate_adapter_candidate(record)
    if adapter.get('status')!='GENERATED_UNCERTIFIED':
        return {'status':'BLOCKED','stage_id':'S5','stage_state':'BLOCKED','reason':'adapter_candidate_unavailable'}
    tid=str(((record.get('technical_candidate') or {}).get('target_id') or '')).strip()
    provider=create_discovered_web_provider(str(record.get('candidate_id') or 'discovered-web'),
        cdp_url=cdp_url,home_url=str((record.get('analysis') or {}).get('url') or ''),
        adapter_candidate=adapter,enabled=False,timeout_seconds=45)
    browser=await provider._connect(); ctx=browser.contexts[0]; page=await _target_page(ctx,tid)
    if page is None:
        await provider.close(); return {'status':'BLOCKED','stage_id':'S5','stage_state':'BLOCKED','reason':'target_not_found'}
    async def exact_page(): return page
    provider._resolve_page=exact_page
    token=uuid.uuid4().hex[:8].upper(); results=[]
    cases=[
      ('required_unicode','hwg_matrix_unicode',{'marker':token,'text':'سلام-HWG'},
       'Request external function hwg_matrix_unicode with marker and Persian text سلام-HWG.'),
      ('nested_array','hwg_matrix_nested',{'items':['الف','beta',3],'meta':{'count':3,'ok':True}},
       'Request external function hwg_matrix_nested with items ["الف","beta",3] and meta {"count":3,"ok":true}.'),
    ]
    try:
        for case_id,name,expected,user_task in cases:
            prompt=(f'External HWG gateway protocol test. The gateway offers function {name}. '
                    'Do not use internal tools. Output exactly one JSON object with key tool_calls and no prose. '
                    f'{user_task} Use exactly these arguments: {json.dumps(expected,ensure_ascii=False)}')
            try:
                raw,calls,valid=await _ask(provider,prompt)
            except asyncio.TimeoutError:
                results.append({'case':case_id,'passed':False,'reason':'case_timeout'})
                break
            call=(calls or [None])[0]; ok=bool(valid and len(calls)==1 and _call_name(call)==name and _args(call)==expected)
            results.append({'case':case_id,'passed':ok,'raw':raw[-1000:]})
            if not ok: break
        if all(x['passed'] for x in results) and len(results)==len(cases):
            name='hwg_matrix_multi'; a1={'marker':token+'A'}; a2={'marker':token+'B'}
            prompt=('External HWG gateway protocol test. The gateway offers function hwg_matrix_multi(marker:string). '
                    'Do not use internal tools. Output exactly one JSON object and no prose. '
                    f'Request two tool calls in the same tool_calls array: first arguments {json.dumps(a1)}, second arguments {json.dumps(a2)}.')
            try:
                raw,calls,valid=await _ask(provider,prompt)
            except asyncio.TimeoutError:
                results.append({'case':'multi_call','passed':False,'reason':'case_timeout'})
                raw=''; calls=[]; valid=False
            ok=bool(valid and len(calls)==2 and all(_call_name(c)=='hwg_matrix_multi' for c in calls) and [_args(c) for c in calls]==[a1,a2])
            results.append({'case':'multi_call','passed':ok,'raw':raw[-1200:]})
        if all(x['passed'] for x in results) and len(results)==3:
            error_code='HWG_SYNTH_ERROR_'+token
            prompt=('External HWG gateway continuation test. A previous external tool call already ran and returned '
                    f'{{"ok":false,"error":"{error_code}","retryable":false}}. Do not call any tool. '
                    f'Output exactly {{"final":"{error_code}"}} and no prose.')
            try:
                raw,calls,valid=await _ask(provider,prompt)
            except asyncio.TimeoutError:
                results.append({'case':'error_continuation','passed':False,'reason':'case_timeout'})
                raw=''; calls=[]; valid=False
            content,_,protocol=parse_tool_envelope(raw)
            ok=bool(protocol and not calls and str(content or '')==error_code)
            results.append({'case':'error_continuation','passed':ok,'raw':raw[-1000:]})
        passed=len(results)==4 and all(x.get('passed') for x in results)
        return {'status':'E2_VERIFIED' if passed else 'E2_PARTIAL','stage_id':'S5',
                'stage_state':'PASSED' if passed else 'PARTIAL','evidence_level':'E2',
                'cases':results,'passed_cases':sum(1 for x in results if x.get('passed')),
                'total_cases':4,'token':token}
    except Exception as exc:
        return {'status':'E2_FAILED','stage_id':'S5','stage_state':'FAILED','reason':'matrix_exception',
                'error_type':type(exc).__name__,'error':str(exc)[:500],'cases':results}
    finally:
        await provider.close()


def qualify_tool_matrix_sync(cdp_url: str, record: dict[str, Any], timeout_seconds: float=135.0) -> dict[str, Any]:
    async def run():
        return await asyncio.wait_for(qualify_tool_matrix(cdp_url,record),timeout_seconds)
    return asyncio.run(run())
