#!/usr/bin/env python3
"""Agent-Driven UI E2E for hwg-next-1.0.0 panel (Gate 24 analogue)."""
import asyncio, json, sys
from playwright.async_api import async_playwright

BASE = "http://127.0.0.1:5080"
results = []


async def check(page, name, url, selector=None, tokens=()):
    try:
        r = await page.goto(url, wait_until="domcontentloaded", timeout=15000)
        ok = r and r.status == 200
        detail = f"http={r.status if r else 'none'}"
        if ok and selector:
            try:
                await page.wait_for_selector(selector, timeout=8000)
                detail += f" sel={selector}:found"
            except Exception:
                ok = False
                detail += f" sel={selector}:MISSING"
        if ok and tokens:
            content = await page.content()
            for t in tokens:
                if t not in content:
                    ok = False
                    detail += f" missing:{t[:24]}"
        results.append({"name": name, "ok": bool(ok), "detail": detail})
        print(f"[{'PASS' if ok else 'FAIL'}] {name} {detail}")
    except Exception as e:
        results.append({"name": name, "ok": False, "detail": str(e)[:120]})
        print(f"[FAIL] {name} {e}")


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            executable_path="C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
            args=["--no-first-run", "--no-default-browser-check"])
        page = await browser.new_page()
        await check(page, "panel-shell", f"{BASE}/panel/", ".app-shell", ['lang="fa"', 'dir="rtl"'])
        await check(page, "panel-nav", f"{BASE}/panel/", ".nav")
        for name, url in [("api-models", f"{BASE}/v1/models"),
                          ("api-providers", f"{BASE}/v1/providers"),
                          ("api-capabilities", f"{BASE}/v1/capabilities")]:
            try:
                data = await page.evaluate(f"fetch('{url}').then(r=>r.status+':'+r.headers.get('content-type'))")
                ok = data.startswith("200")
                results.append({"name": name, "ok": ok, "detail": data[:80]})
                print(f"[{'PASS' if ok else 'FAIL'}] {name} {data[:80]}")
            except Exception as e:
                results.append({"name": name, "ok": False, "detail": str(e)[:100]})
                print(f"[FAIL] {name} {e}")
        await browser.close()
    passed = sum(1 for r in results if r["ok"])
    with open(".runtime/ui-e2e-100dev1.json", "w", encoding="utf-8") as f:
        json.dump({"passed": passed, "total": len(results), "results": results}, f, ensure_ascii=False, indent=2)
    print(f"\n{passed}/{len(results)} panel E2E checks passed")
    return passed == len(results)


sys.exit(0 if asyncio.run(main()) else 1)
