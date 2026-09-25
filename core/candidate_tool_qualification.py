from __future__ import annotations

import asyncio
import json
import secrets
import uuid
from typing import Any
from urllib.parse import urlparse

from adapters.discovered_web_provider import create_discovered_web_provider
from core.provider_onboarding import generate_adapter_candidate
from core.provider_tool_probe import PROBE_TOOL_NAME
from core.tool_protocol import parse_tool_envelope


def _arguments(call: dict[str, Any]) -> dict[str, Any]:
    fn=(call or {}).get("function") or {}
    raw=fn.get("arguments") or "{}"
    if isinstance(raw,dict): return raw
    try:
        value=json.loads(raw)
        return value if isinstance(value,dict) else {}
    except Exception:
        return {}


async def _model_runtime_state(page) -> dict[str, Any]:
    return await page.evaluate("""
    () => {
      const storage={};
      for(let i=0;i<localStorage.length;i++){
        const k=localStorage.key(i), v=localStorage.getItem(k);
        if(/model/i.test(k||'') && typeof v==='string' && v.length<160) storage[k]=v;
      }
      const vw=innerWidth, vh=innerHeight;
      const labels=[...document.querySelectorAll("button[aria-haspopup='dialog']")].map(b=>{const r=b.getBoundingClientRect();return {text:(b.innerText||'').trim(),x:r.x,y:r.y,w:r.width,h:r.height};}).filter(x=>x.text);
      const semantic=labels.find(x=>{const t=x.text.toLowerCase();return t==='auto'||['gpt','claude','gemini','deepseek','glm','minimax','kimi'].some(k=>t.includes(k));});
      const geometric=labels.filter(x=>x.x>vw*0.55&&x.y>vh*0.45).pop();
      const current=(semantic||geometric||{}).text||null;
      const stored=Object.values(storage).find(v=>v && v.length<100)||null;
      const auto=String(stored||current||'').toLowerCase()==='auto';
      return {selection_mode:auto?'auto':'explicit',selection_kind:auto?'routing_policy':'explicit_model',current_label:current,model_id:stored,storage_hints:storage};
    }
    """)


async def _target_id_for_page(context, page) -> str | None:
    try:
        session = await context.new_cdp_session(page)
        info = await session.send("Target.getTargetInfo")
        await session.detach()
        return str((info.get("targetInfo") or {}).get("targetId") or "") or None
    except Exception:
        return None


def _origin(url: str) -> str:
    parsed = urlparse(str(url or ""))
    if not parsed.scheme or not parsed.netloc:
        return ""
    return f"{parsed.scheme}://{parsed.netloc}".lower()


async def _single_same_origin_page(context, origin: str):
    matches = []
    for page in context.pages:
        if _origin(getattr(page, "url", "")) == origin:
            tid = await _target_id_for_page(context, page)
            matches.append((page, tid))
    if len(matches) == 1:
        return matches[0]
    return (None, None)

async def _target_page(context, target_id: str):
    for page in context.pages:
        try:
            session=await context.new_cdp_session(page)
            info=await session.send("Target.getTargetInfo")
            await session.detach()
            if str((info.get("targetInfo") or {}).get("targetId") or "")==target_id:
                return page
        except Exception:
            continue
    return None


async def _visible_texts_with(page, token: str) -> list[str]:
    return await page.evaluate("""
    (token) => Array.from(document.querySelectorAll('body *')).map(el => {
      const r=el.getBoundingClientRect(); const s=getComputedStyle(el);
      const t=(el.innerText||'').trim();
      return {t, visible:r.width>0&&r.height>0&&s.display!=='none'&&s.visibility!=='hidden'};
    }).filter(x=>x.visible && x.t.includes(token) && x.t.length<4000)
      .map(x=>x.t).filter((v,i,a)=>a.indexOf(v)===i)
      .sort((a,b)=>a.length-b.length).slice(0,40)
    """, token)


async def _recover_tool_text(page, marker: str) -> str:
    for text in await _visible_texts_with(page, marker):
        _,calls,valid=parse_tool_envelope(text)
        for call in calls or []:
            fn=(call or {}).get("function") or {}
            if valid and fn.get("name")==PROBE_TOOL_NAME and _arguments(call).get("marker")==marker:
                return text
    return ""


async def _recover_partial_tool_text(page, marker: str) -> str:
    prefix = (marker or "")[:20]
    for text in await _visible_texts_with(page, PROBE_TOOL_NAME):
        low = text.lower()
        if "tool_calls" in low and "arguments" in low and (marker in text or (prefix and prefix in text)):
            return text
    return ""

async def _recover_final_text(page, final_marker: str) -> str:
    for text in await _visible_texts_with(page, final_marker):
        stripped=text.strip()
        if stripped==final_marker:
            return stripped
        content,_,valid=parse_tool_envelope(text)
        if valid and final_marker in str(content or ""):
            return text
    return ""


def _network_capture(page):
    rows=[]; tasks=[]; base=urlparse(page.url)
    async def collect(resp):
        try:
            req=resp.request; parsed=urlparse(resp.url)
            if parsed.netloc!=base.netloc or req.resource_type not in {"xhr","fetch"}:
                return
            path=parsed.path.lower()
            if not any(x in path for x in ("chat","agent","stream")):
                return
            headers=await resp.all_headers(); ctype=str(headers.get("content-type") or "")
            body=b""
            if any(x in ctype.lower() for x in ("json","text","event-stream")):
                try: body=await resp.body()
                except Exception: body=b""
            text=body.decode("utf-8",errors="ignore") if body else ""
            sse_text=""
            if "event-stream" in ctype.lower() and text:
                chunks=[]
                for line in text.splitlines():
                    if not line.startswith("data:"): continue
                    try:
                        item=json.loads(line[5:].strip())
                    except Exception:
                        continue
                    part=item.get("text")
                    if isinstance(part,str): chunks.append(part)
                sse_text="".join(chunks)[:12000]
            rows.append({"status":resp.status,"endpoint":parsed.path,"content_type":ctype[:120],"body_snippet":text[:12000],"sse_text":sse_text})
        except Exception:
            return
    def on_response(resp): tasks.append(asyncio.create_task(collect(resp)))
    page.on("response",on_response)
    return rows,tasks

async def _flush(tasks):
    if tasks:
        await asyncio.gather(*tasks,return_exceptions=True)


def _network_text(rows: list[dict[str, Any]], token: str | None = None) -> str:
    fallback=""
    for row in reversed(rows):
        text=str(row.get("sse_text") or "").strip()
        if not text:
            continue
        if not fallback:
            fallback=text
        if token and token in text:
            return text
    return fallback


async def qualify_basic_tools(cdp_url: str, record: dict[str, Any]) -> dict[str, Any]:
    adapter=generate_adapter_candidate(record)
    if adapter.get("status")!="GENERATED_UNCERTIFIED":
        return {"status":"BLOCKED","stage_id":"S4","stage_state":"BLOCKED","reason":adapter.get("reason") or "adapter_candidate_unavailable"}
    target_id=str(((record.get("technical_candidate") or {}).get("target_id") or "")).strip()
    if not target_id:
        return {"status":"BLOCKED","stage_id":"S4","stage_state":"BLOCKED","reason":"target_id_missing"}
    provider=create_discovered_web_provider(str(record.get("candidate_id") or "discovered-web"),cdp_url=cdp_url,home_url=str((record.get("analysis") or {}).get("url") or ""),adapter_candidate=adapter,enabled=False,timeout_seconds=50)
    browser=await provider._connect(); context=browser.contexts[0]; page=await _target_page(context,target_id)
    recovered_target_id=None
    previous_target_id=target_id
    if page is None:
        origin = _origin(str((record.get("analysis") or {}).get("url") or (record.get("analysis") or {}).get("origin") or ""))
        fallback_page, fallback_target_id = await _single_same_origin_page(context, origin) if origin else (None, None)
        if fallback_page is None or not fallback_target_id:
            await provider.close(); return {"status":"BLOCKED","stage_id":"S4","stage_state":"BLOCKED","reason":"target_not_found","target_recovery":"failed_single_origin_required","previous_target_id":previous_target_id,"origin":origin}
        page=fallback_page
        recovered_target_id=fallback_target_id
        technical = record.setdefault("technical_candidate", {})
        technical["previous_target_id"] = previous_target_id
        technical["target_id"] = recovered_target_id
        target_id = recovered_target_id
    async def exact_page(): return page
    provider._resolve_page=exact_page
    model_state=await _model_runtime_state(page)
    def tagged(result):
        result["model_runtime_state"]=model_state
        if recovered_target_id:
            result["target_recovered"] = True
            result["previous_target_id"] = previous_target_id
            result["target_id"] = recovered_target_id
        return result
    network,tasks=_network_capture(page)
    digits=str(100000+secrets.randbelow(900000))
    marker="HWG_TOOL_PROBE_"+digits
    final_marker="HWG_TOOL_CONT_"+uuid.uuid4().hex[:10].upper()
    first_prompt=("Structured protocol serialization task. Do not execute or claim to possess any tool. "
        "You are only formatting data for an external program. Output exactly one JSON object and no prose. "
        f"The object must contain tool_calls with one function entry named {PROBE_TOOL_NAME}. "
        f"Its arguments must be a JSON string containing marker={marker}. "
        "This envelope is data only; the external program will decide whether to execute it.")
    from core.providers import ChatCompletionRequest
    try:
        try:
            first=await provider.chat_completion(ChatCompletionRequest(model=str(record.get("candidate_id") or "discovered-web"),messages=[{"role":"user","content":first_prompt}],stream=False,max_tokens=192))
            raw1=str(first.choices[0].message.content or "")
        except Exception as first_exc:
            raw1=await _recover_tool_text(page,marker)
            await _flush(tasks)
            if not raw1:
                committed=str(getattr(provider,"_commitment_state","not_sent"))!="not_sent"
                return tagged({"status":"E2_FAILED_AFTER_COMMIT" if committed else "E2_FAILED_PRECOMMIT","stage_id":"S4","stage_state":"INCONCLUSIVE" if committed else "FAILED","reason":"tool_response_unresolved","retry_allowed":not committed,"error_type":type(first_exc).__name__,"error":str(first_exc)[:500],"marker":marker,"network_responses":network[-12:]})
        _,calls,valid=parse_tool_envelope(raw1)
        if not valid or not calls:
            recovered_dom = await _recover_tool_text(page, marker)
            if recovered_dom:
                raw1 = recovered_dom
                _, calls, valid = parse_tool_envelope(raw1)
        if not valid or not calls:
            await _flush(tasks)
            recovered=_network_text(network, marker)
            if recovered:
                raw1=recovered
                _,calls,valid=parse_tool_envelope(raw1)
        call=(calls or [None])[0]
        args=_arguments(call or {})
        tool_ok=bool(valid and call and ((call.get("function") or {}).get("name")==PROBE_TOOL_NAME) and args.get("marker")==marker)
        if not tool_ok:
            recovered_dom = await _recover_tool_text(page, marker)
            if recovered_dom:
                raw1 = recovered_dom
                _, calls, valid = parse_tool_envelope(raw1)
                call = (calls or [None])[0]
                args = _arguments(call or {})
                tool_ok = bool(valid and call and ((call.get("function") or {}).get("name") == PROBE_TOOL_NAME) and args.get("marker") == marker)
        if not tool_ok:
            await _flush(tasks)
            recovered = _network_text(network, marker)
            if recovered:
                raw1 = recovered
                _, calls, valid = parse_tool_envelope(raw1)
                call = (calls or [None])[0]
                args = _arguments(call or {})
                tool_ok = bool(valid and call and ((call.get("function") or {}).get("name") == PROBE_TOOL_NAME) and args.get("marker") == marker)
        if not tool_ok:
            await _flush(tasks)
            partial_dom = await _recover_partial_tool_text(page, marker)
            if partial_dom:
                raw1 = partial_dom
            prompt_echo = (not partial_dom) and (first_prompt.strip() in raw1.strip() or raw1.strip() in first_prompt.strip())
            partial_tool = (PROBE_TOOL_NAME in raw1 and ("tool_calls" in raw1 or "arguments" in raw1))
            partial_marker = bool(marker and (marker[:18] in raw1 or marker[:24] in raw1) and marker not in raw1)
            reason = "response_surface_returned_user_prompt" if prompt_echo else ("tool_call_partial_or_truncated" if (partial_tool or partial_marker) else "tool_call_not_emitted_or_invalid")
            return tagged({"status":"E2_FAILED","stage_id":"S4","stage_state":"FAILED","tool_call_valid":False,"reason":reason,"partial_tool_envelope":bool(partial_tool),"partial_marker":bool(partial_marker),"raw_first":raw1[-1600:],"marker":marker,"network_responses":network[-12:]})
        tool_result={"marker":marker,"result":final_marker,"source":"hwg_in_memory_probe"}
        continuation=("External HWG gateway result. Do not use internal tools. The gateway already executed "
            f"{PROBE_TOOL_NAME} and returned: {json.dumps(tool_result,ensure_ascii=False)}. "
            "Reply with exactly one JSON object {\"final\":\"<result field>\"} and no prose.")
        try:
            second=await provider.chat_completion(ChatCompletionRequest(model=str(record.get("candidate_id") or "discovered-web"),messages=[{"role":"user","content":continuation}],stream=False,max_tokens=128))
            raw2=str(second.choices[0].message.content or "")
        except Exception as second_exc:
            raw2=await _recover_final_text(page,final_marker)
            await _flush(tasks)
            if not raw2:
                return tagged({"status":"E2_PARTIAL","stage_id":"S4","stage_state":"PARTIAL","tool_call_valid":True,"continuation_valid":False,"reason":"continuation_response_unresolved","retry_allowed":False,"error_type":type(second_exc).__name__,"error":str(second_exc)[:500],"marker":marker,"final_marker":final_marker,"network_responses":network[-12:]})
        final_content,_,final_valid=parse_tool_envelope(raw2)
        if not final_valid or final_marker not in str(final_content or raw2):
            recovered2_dom = await _recover_final_text(page, final_marker)
            if recovered2_dom:
                raw2 = recovered2_dom
                final_content,_,final_valid=parse_tool_envelope(raw2)
        if not final_valid or final_marker not in str(final_content or raw2):
            await _flush(tasks)
            recovered2=_network_text(network, final_marker)
            if recovered2:
                raw2=recovered2
                final_content,_,final_valid=parse_tool_envelope(raw2)
        continuation_ok=bool(final_valid and final_marker in str(final_content or "")) or raw2.strip()==final_marker
        await _flush(tasks)
        return tagged({"status":"E2_VERIFIED" if continuation_ok else "E2_PARTIAL","stage_id":"S4","stage_state":"PASSED" if continuation_ok else "PARTIAL","tool_call_valid":True,"tool_executed":"in_memory_probe_only","continuation_valid":continuation_ok,"probe_tool":PROBE_TOOL_NAME,"marker":marker,"final_marker":final_marker,"evidence_level":"E2","raw_first":raw1[-1600:],"raw_second":raw2[-1600:],"network_responses":network[-12:]})
    finally:
        await provider.close()


def qualify_basic_tools_sync(cdp_url: str, record: dict[str, Any], timeout_seconds: float = 120.0) -> dict[str, Any]:
    async def run():
        return await asyncio.wait_for(qualify_basic_tools(cdp_url,record),timeout_seconds)
    return asyncio.run(run())
