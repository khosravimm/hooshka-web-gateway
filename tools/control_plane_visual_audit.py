from __future__ import annotations
import asyncio, json, re
from datetime import datetime, timezone
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from playwright.async_api import async_playwright
from core.visual_discovery import capture_user_view, visible_interaction_map

OUT=ROOT/'.runtime-dev'/('control-plane-visual-audit-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
SAFE_RE=re.compile(r'(تازه|refresh|probe|بررسی|مشاهده|جزئیات|نمایش|بازخوان|retry|test)',re.I)
DANGER_RE=re.compile(r'(حذف|delete|restart|ری.?استارت|stop|توقف|start|شروع|save|ذخیره|create|ایجاد|reset|پاک|open browser|باز کردن مرورگر)',re.I)


async def dynamic_signature(page, pending):
    state=await page.locator('main').evaluate(r"""root=>{
      const vis=e=>{const r=e.getBoundingClientRect(),s=getComputedStyle(e);return r.width>0&&r.height>0&&s.display!=='none'&&s.visibility!=='hidden'};
      const text=(root.innerText||'').trim();
      const controls=[...root.querySelectorAll('button,input,select,textarea,[role=button]')].filter(vis);
      const loaders=[...root.querySelectorAll('[aria-busy=true],.loading,.spinner,[class*=loading],[class*=spinner]')].filter(vis);
      const placeholders=(text.match(/(?:بررسی\.\.\.|در حال بار|loading|initializing|^-$|\t-\t)/gim)||[]).length;
      return {text_len:text.length,controls:controls.length,loaders:loaders.length,placeholders,tail:text.slice(-1200)};
    }""")
    state['pending']=len(pending)
    return state

async def wait_dynamic_ready(page, pending, panel, timeout=25.0):
    loop=asyncio.get_running_loop(); started=loop.time(); deadline=started+timeout
    trace=[]; last=None; stable_since=None
    while loop.time()<deadline:
        sig=await dynamic_signature(page,pending); now=loop.time()
        compact=(sig['text_len'],sig['controls'],sig['loaders'],sig['placeholders'],sig['pending'])
        if compact!=last:
            trace.append({'at':round(now,3),**sig}); last=compact; stable_since=now
        quiet=sig['pending']==0 and sig['loaders']==0
        populated=sig['text_len']>80
        if quiet and populated and now-started>=4.0 and stable_since is not None and now-stable_since>=2.0:
            return {'ready':True,'panel':panel,'waited':round(timeout-(deadline-now),2),'final':sig,'trace':trace}
        await page.wait_for_timeout(400)
    sig=await dynamic_signature(page,pending)
    return {'ready':False,'panel':panel,'waited':timeout,'final':sig,'trace':trace,'reason':'dynamic_settle_timeout'}


async def capture_scroll_sweep(page, panel):
    dims=await page.evaluate("() => ({h:document.documentElement.scrollHeight,v:innerHeight})")
    maxy=max(0,int(dims['h'])-int(dims['v']))
    ys=sorted(set([0, maxy//2, maxy]))
    out=[]
    for idx,y in enumerate(ys):
        await page.evaluate('(y)=>scrollTo(0,y)',y); await page.wait_for_timeout(700)
        out.append(await capture_user_view(page,'control-plane',f'{panel}-scroll-{idx}',root=OUT))
    await page.evaluate('()=>scrollTo(0,0)'); await page.wait_for_timeout(300)
    return out

async def main():
    OUT.mkdir(parents=True,exist_ok=True)
    console_errors=[]; failed_requests=[]; results=[]
    async with async_playwright() as pw:
        browser=await pw.chromium.connect_over_cdp('http://127.0.0.1:9330')
        context=browser.contexts[0]
        page=await context.new_page()
        await page.set_viewport_size({'width':1440,'height':1000})
        pending=set()
        page.on('console',lambda m: console_errors.append({'type':m.type,'text':m.text}) if m.type=='error' else None)
        page.on('request',lambda r: pending.add(r) if r.resource_type in {'fetch','xhr'} else None)
        page.on('requestfinished',lambda r: pending.discard(r))
        def _failed(r):
            pending.discard(r); failed_requests.append({'url':r.url,'failure':r.failure})
        page.on('requestfailed',_failed)
        await page.goto('http://127.0.0.1:5080/panel/',wait_until='domcontentloaded',timeout=30000)
        await wait_dynamic_ready(page,pending,'overview-initial')
        navs=await page.locator('.nav-item[data-panel]').evaluate_all("els=>els.map(e=>({panel:e.dataset.panel,label:e.innerText.trim()}))")
        for nav in navs:
            panel=nav['panel']; label=nav['label']
            c0=len(console_errors); f0=len(failed_requests)
            await page.locator(f'.nav-item[data-panel="{panel}"]').click()
            entered=await capture_user_view(page,'control-plane',f'{panel}-entered',root=OUT)
            readiness=await wait_dynamic_ready(page,pending,panel)
            settled=await capture_user_view(page,'control-plane',f'{panel}-settled',root=OUT)
            await page.wait_for_timeout(1200)
            confirm=await wait_dynamic_ready(page,pending,panel+'-confirm',timeout=8.0)
            before=await capture_user_view(page,'control-plane',f'{panel}-before-interaction',root=OUT)
            scroll_views=await capture_scroll_sweep(page,panel)
            imap=await visible_interaction_map(page)
            interactions=[]
            main=page.locator('main')
            selects=main.locator('select:visible')
            for i in range(min(await selects.count(),2)):
                sel=selects.nth(i)
                opts=await sel.locator('option').evaluate_all("xs=>xs.map(x=>({value:x.value,text:x.textContent.trim(),disabled:x.disabled}))")
                old=await sel.input_value(); alt=next((o for o in opts if not o['disabled'] and o['value']!=old),None)
                if alt:
                    try:
                        await sel.select_option(alt['value'])
                        gate=await wait_dynamic_ready(page,pending,panel+'-select-change',timeout=12.0)
                        shot=await capture_user_view(page,'control-plane',f'{panel}-select-{i}-changed',root=OUT)
                        interactions.append({'kind':'select','id':await sel.get_attribute('id'),'from':old,'to':alt['value'],'result':'changed_then_restored','gate':gate,'screenshot':shot.get('screenshot')})
                        await sel.select_option(old); await wait_dynamic_ready(page,pending,panel+'-select-restore',timeout=12.0)
                    except Exception as exc:
                        interactions.append({'kind':'select','id':await sel.get_attribute('id'),'result':'error','error':type(exc).__name__})
            buttons=main.locator('button:visible:not(.nav-item)')
            for i in range(await buttons.count()):
                b=buttons.nth(i); txt=((await b.inner_text()) or (await b.get_attribute('title')) or '').strip()
                if not txt or DANGER_RE.search(txt) or not SAFE_RE.search(txt) or await b.is_disabled(): continue
                try:
                    timeout=60.0 if re.search(r'(probe|readiness|certif|گواهی|آمادگی|تست)',txt,re.I) else 15.0
                    await b.click(); gate=await wait_dynamic_ready(page,pending,panel+'-button',timeout=timeout)
                    shot=await capture_user_view(page,'control-plane',f'{panel}-button-{i}',root=OUT)
                    interactions.append({'kind':'button','text':txt[:100],'result':'clicked','gate':gate,'screenshot':shot.get('screenshot')})
                except Exception as exc:
                    interactions.append({'kind':'button','text':txt[:100],'result':'error','error':type(exc).__name__})
                if len([x for x in interactions if x['kind']=='button'])>=2: break
            final_gate=await wait_dynamic_ready(page,pending,panel+'-final',timeout=12.0)
            after=await capture_user_view(page,'control-plane',f'{panel}-after-interaction',root=OUT)
            aftermap=await visible_interaction_map(page)
            results.append({'panel':panel,'label':label,'entered':entered,'readiness':readiness,'settled':settled,'confirm':confirm,'before':before,'scroll_views':scroll_views,'interaction_map':imap,'interactions':interactions,'final_gate':final_gate,'after':after,'after_map':aftermap,'console_errors':console_errors[c0:],'request_failures':failed_requests[f0:]})
        # global theme transition as a user-visible control
        theme=page.locator('#theme-toggle')
        if await theme.count():
            await theme.click(); await page.wait_for_timeout(300); await capture_user_view(page,'control-plane','theme-toggled',root=OUT)
            await theme.click(); await page.wait_for_timeout(250)
        await page.close()
        await browser.close()
    (OUT/'audit.json').write_text(json.dumps({'generated_at':datetime.now(timezone.utc).isoformat(),'panels':results},ensure_ascii=False,indent=2),encoding='utf-8')
    print(str(OUT)); print(json.dumps([{'panel':x['panel'],'label':x['label'],'controls':len(x['interaction_map']['controls']),'headings':len(x['interaction_map']['headings']),'overflow':x['interaction_map']['horizontal_overflow'],'clipped':len(x['interaction_map']['clipped']),'interactions':x['interactions'],'console_errors':len(x['console_errors']),'request_failures':len(x['request_failures'])} for x in results],ensure_ascii=False))

if __name__=='__main__': asyncio.run(main())