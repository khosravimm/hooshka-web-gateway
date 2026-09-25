import asyncio
from typing import Any
from core.candidate_tool_qualification import _target_page, _model_runtime_state

ROW_JS = r"""([text,left,w])=>[...document.querySelectorAll('body *')].map(e=>{const r=e.getBoundingClientRect();const t=(e.innerText||'').trim().replace(/\s+/g,' ');return {t,x:r.x,y:r.y,w:r.width,h:r.height}}).filter(x=>x.t===text&&x.w>70&&x.h>24&&(left?x.x<w*.70:x.x>w*.45)).sort((a,b)=>(a.w*a.h)-(b.w*b.h))"""
MODEL_JS = r"""(name)=>[...document.querySelectorAll('body *')].map(e=>{const r=e.getBoundingClientRect();const t=(e.innerText||'').trim().replace(/\s+/g,' ');return {t,x:r.x,y:r.y,w:r.width,h:r.height}}).filter(x=>x.t.startsWith(name)&&x.w>100&&x.h>24&&x.x>innerWidth*.45).sort((a,b)=>(a.w*a.h)-(b.w*b.h))"""

async def _model_trigger(page):
    vp=page.viewport_size or {'width':1280,'height':800}
    locs=page.locator("button[aria-haspopup='dialog']")
    semantic=[]; fallback=[]
    for i in range(await locs.count()):
        loc=locs.nth(i); box=await loc.bounding_box(); text=(await loc.inner_text()).strip()
        if not box: continue
        low=text.lower()
        if low=='auto' or any(x in low for x in ('gpt','claude','gemini','deepseek','glm','minimax','kimi')): semantic.append(loc)
        if box['x']>vp['width']*.55 and box['y']>vp['height']*.45: fallback.append(loc)
    return semantic[0] if semantic else (fallback[-1] if fallback else None)

async def _wait_trigger(page):
    for _ in range(20):
        loc=await _model_trigger(page)
        if loc is not None: return loc
        await page.wait_for_timeout(250)
    return None
async def _click_text_row(page,text:str,left_side:bool):
    vp=page.viewport_size or {'width':1280,'height':800}
    for _ in range(12):
        rows=await page.evaluate(ROW_JS,[text,left_side,vp['width']])
        if rows:
            r=rows[0]; await page.mouse.click(r['x']+r['w']/2,r['y']+r['h']/2)
            await page.wait_for_timeout(250); return True
        await page.wait_for_timeout(250)
    return False

async def select_model(cdp_url:str,target_id:str,label:str,category:str|None=None)->dict[str,Any]:
    from playwright.async_api import async_playwright
    pw=await async_playwright().start(); browser=await pw.chromium.connect_over_cdp(cdp_url)
    try:
        ctx=browser.contexts[0]; page=await _target_page(ctx,target_id)
        if page is None: return {'status':'BLOCKED','reason':'target_not_found'}
        from core.visual_discovery import visual_action_gate
        visual={}
        for _ in range(40):
            visual=await visual_action_gate(page,'provider_interaction')
            if visual.get('allowed'): break
            await page.wait_for_timeout(250)
        if not visual.get('allowed'):
            return {'status':'BLOCKED','reason':'model_surface_not_visual_ready','classification':visual.get('classification') or {}}
        before=await _model_runtime_state(page); trigger=await _wait_trigger(page)
        if trigger is None: return {'status':'BLOCKED','reason':'model_trigger_missing','before':before}
        await trigger.click(force=True); await page.wait_for_timeout(250)
        if category and not await _click_text_row(page,category,True):
            try: await page.keyboard.press('Escape')
            except Exception: pass
            return {'status':'BLOCKED','reason':'model_category_missing','before':before}
        rows=[]
        for _ in range(12):
            rows=await page.evaluate(MODEL_JS,label)
            if rows: break
            await page.wait_for_timeout(250)
        if not rows:
            try: await page.keyboard.press('Escape')
            except Exception: pass
            return {'status':'BLOCKED','reason':'model_row_missing','before':before}
        r=rows[0]; await page.mouse.click(r['x']+r['w']/2,r['y']+r['h']/2); await page.wait_for_timeout(500)
        after=await _model_runtime_state(page)
        return {'status':'SELECTED','before':before,'after':after,'label':label,'category':category}
    finally:
        await pw.stop()

async def restore_auto(cdp_url:str,target_id:str)->dict[str,Any]:
    from playwright.async_api import async_playwright
    pw=await async_playwright().start(); browser=await pw.chromium.connect_over_cdp(cdp_url)
    try:
        ctx=browser.contexts[0]; page=await _target_page(ctx,target_id)
        if page is None: return {'status':'BLOCKED','reason':'target_not_found'}
        trigger=await _wait_trigger(page)
        if trigger is None: return {'status':'BLOCKED','reason':'model_trigger_missing'}
        await trigger.click(force=True); await page.wait_for_timeout(250)
        if not await _click_text_row(page,'Auto',True): return {'status':'BLOCKED','reason':'auto_row_missing'}
        await page.wait_for_timeout(400)
        return {'status':'RESTORED','after':await _model_runtime_state(page)}
    finally:
        await pw.stop()

def select_model_sync(cdp_url:str,target_id:str,label:str,category:str|None=None)->dict[str,Any]:
    return asyncio.run(select_model(cdp_url,target_id,label,category))

def restore_auto_sync(cdp_url:str,target_id:str)->dict[str,Any]:
    return asyncio.run(restore_auto(cdp_url,target_id))
