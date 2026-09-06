import os
from playwright.sync_api import sync_playwright

CDP_URL = os.getenv("BRIDGE_CDP_URL", "http://127.0.0.1:9222")
CHATGPT_URL = "https://chatgpt.com"


def get_page():
    pw = sync_playwright().start()
    browser = pw.chromium.connect_over_cdp(CDP_URL)
    context = browser.contexts[0] if browser.contexts else None
    if not context:
        raise Exception("Browser context not found")

    page = None
    for p in context.pages:
        if "chatgpt.com" in p.url:
            page = p
            break

    if not page:
        page = context.new_page()
        page.goto(CHATGPT_URL, wait_until="domcontentloaded", timeout=30000)

    return page, pw, browser
