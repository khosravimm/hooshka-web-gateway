import asyncio
import time
from typing import AsyncIterator, Optional

from playwright.async_api import Browser, BrowserContext, Page, Playwright, async_playwright

from core.providers import ProviderAuthError, ProviderError, ProviderTimeoutError


class DeepSeekBrowserUITransport:
    """Controlled DeepSeek Web Chat UI transport.

    This transport intentionally uses the visible Web Chat session instead of a
    copied token/API backend. It does not bypass CAPTCHA, suspension, mute, or
    other provider controls. Completion is reconstructed from the latest visible
    assistant message.
    """

    def __init__(
        self,
        provider_id: str,
        *,
        cdp_url: str = "http://127.0.0.1:9223",
        base_url: str = "https://chat.deepseek.com/",
        launch_timeout: float = 45.0,
        first_event_timeout: float = 45.0,
        idle_timeout: float = 90.0,
        total_timeout: float = 180.0,
        poll_interval: float = 0.5,
    ) -> None:
        self.provider_id = provider_id
        self.cdp_url = cdp_url
        self.base_url = base_url
        self.launch_timeout = launch_timeout
        self.first_event_timeout = first_event_timeout
        self.idle_timeout = idle_timeout
        self.total_timeout = total_timeout
        self.poll_interval = poll_interval
        self._pw: Optional[Playwright] = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None
        self._lock = asyncio.Lock()
        self.last_session_mode: Optional[str] = None
        self.last_conversation_url: Optional[str] = None
        self.last_block_signals: dict = {}
        self.last_assistant_text: Optional[str] = None

    async def _ensure(self) -> Page:
        if self._page and not self._page.is_closed():
            try:
                if await self._page.evaluate("() => location.hostname === 'chat.deepseek.com'"):
                    return self._page
            except Exception:
                pass
        if self._pw is None:
            self._pw = await async_playwright().start()
        try:
            self._browser = await self._pw.chromium.connect_over_cdp(self.cdp_url, timeout=self.launch_timeout * 1000)
        except Exception as exc:
            raise ProviderError(
                "DeepSeek browser CDP endpoint is unavailable",
                "browser_cdp_unavailable",
                self.provider_id,
                {"cdp_url": self.cdp_url},
            ) from exc
        contexts = self._browser.contexts
        if not contexts:
            self._context = await self._browser.new_context()
            self._page = await self._context.new_page()
            await self._page.goto(self.base_url, wait_until="domcontentloaded", timeout=self.launch_timeout * 1000)
        else:
            # CDP may expose multiple contexts. The authenticated tab belongs to
            # the user's real Chrome profile, which is not guaranteed to be the
            # first context. Search every context/page before opening a new tab.
            self._context = contexts[0]
            self._page = None
            for ctx in contexts:
                for candidate in [p for p in ctx.pages if not p.is_closed()]:
                    try:
                        if "chat.deepseek.com" in candidate.url:
                            self._context = ctx
                            self._page = candidate
                            break
                    except Exception:
                        pass
                if self._page is not None:
                    break
            if self._page is None:
                self._page = await self._context.new_page()
                await self._page.goto(self.base_url, wait_until="domcontentloaded", timeout=self.launch_timeout * 1000)
            elif "chat.deepseek.com" not in self._page.url:
                await self._page.goto(self.base_url, wait_until="domcontentloaded", timeout=self.launch_timeout * 1000)
        await self._page.wait_for_timeout(1000)
        return self._page

    async def _body_text(self, page: Page) -> str:
        try:
            return await page.evaluate("() => document.body ? document.body.innerText : ''")
        except Exception:
            return ""

    @staticmethod
    def _block_signals(text: str, *, textarea_count: int = 0, url: str = "") -> dict:
        low = (text or "").lower()
        url_low = (url or "").lower()
        captcha = any(x in low for x in ["verify you are human", "security check", "cloudflare", "captcha challenge"])
        suspended_or_muted = any(
            x in low
            for x in [
                "your account has been suspended",
                "account is suspended",
                "temporarily suspended",
                "account has been muted",
                "you are temporarily restricted",
                "violation of usage rules",
            ]
        )
        login = False
        if textarea_count <= 0:
            login = (
                "sign_in" in url_low
                or "sign-in" in url_low
                or any(x in low for x in ["log in to deepseek", "sign in to deepseek", "continue with google", "password"])
            )
        return {
            "captcha": captcha,
            "suspended_or_muted": suspended_or_muted,
            "login": login,
        }

    async def session_status(self) -> dict:
        page = await self._ensure()
        body = await self._body_text(page)
        textarea_count = await page.locator("textarea").count()
        signals = self._block_signals(body, textarea_count=textarea_count, url=page.url)
        deadline = time.monotonic() + min(8.0, self.launch_timeout)
        while textarea_count == 0 and not any(signals.values()) and time.monotonic() < deadline:
            await page.wait_for_timeout(500)
            body = await self._body_text(page)
            textarea_count = await page.locator("textarea").count()
            signals = self._block_signals(body, textarea_count=textarea_count, url=page.url)
        authenticated = textarea_count > 0 and not signals["login"] and not signals["captcha"] and not signals["suspended_or_muted"]
        self.last_session_mode = "authenticated" if authenticated else "blocked_or_guest"
        self.last_block_signals = signals
        return {
            "authenticated": authenticated,
            "mode": self.last_session_mode,
            "url": page.url,
            "title": await page.title(),
            "textarea_count": textarea_count,
            "signals": signals,
        }

    async def health(self) -> bool:
        status = await self.session_status()
        return bool(status.get("authenticated"))

    async def _start_new_chat(self, page: Page) -> None:
        try:
            new_chat = page.get_by_text("New chat").first
            if await new_chat.count() > 0:
                await new_chat.click(timeout=5000)
                await page.wait_for_timeout(1200)
                return
        except Exception:
            pass
        try:
            await page.goto(self.base_url, wait_until="domcontentloaded", timeout=self.launch_timeout * 1000)
            await page.wait_for_timeout(1200)
        except Exception:
            pass

    async def _assistant_messages(self, page: Page) -> list[str]:
        try:
            return await page.locator(".ds-assistant-message-main-content").evaluate_all(
                "nodes => nodes.map(n => (n.innerText || '').trim()).filter(Boolean)"
            )
        except Exception:
            return []

    async def _submit(self, page: Page, prompt: str) -> None:
        textarea = page.locator("textarea").first
        await textarea.wait_for(state="visible", timeout=self.launch_timeout * 1000)
        await textarea.fill(prompt)
        await page.wait_for_timeout(200)
        await textarea.press("Enter")

    async def stream_text(self, prompt: str, *, new_chat: bool = True) -> AsyncIterator[dict]:
        if not prompt.strip():
            raise ProviderError("DeepSeek prompt is empty", "invalid_request", self.provider_id)
        async with self._lock:
            page = await self._ensure()
            status = await self.session_status()
            if not status.get("authenticated"):
                raise ProviderAuthError(self.provider_id, "DeepSeek Web Chat requires an authenticated browser session")
            if new_chat:
                await self._start_new_chat(page)
            before = await self._assistant_messages(page)
            before_count = len(before)
            await self._submit(page, prompt)
            start = time.monotonic()
            first_seen_at: Optional[float] = None
            stable_since: Optional[float] = None
            last_text = ""
            stable_window = min(2.0, self.idle_timeout)
            try:
                while True:
                    now = time.monotonic()
                    if now - start > self.total_timeout:
                        raise ProviderTimeoutError(self.provider_id, "DeepSeek Web Chat completion timed out")
                    body = await self._body_text(page)
                    textarea_count = await page.locator("textarea").count()
                    signals = self._block_signals(body, textarea_count=textarea_count, url=page.url)
                    self.last_block_signals = signals
                    if signals["captcha"] or signals["suspended_or_muted"] or signals["login"]:
                        raise ProviderError(
                            "DeepSeek Web Chat is blocked by provider UI state",
                            "provider_ui_blocked",
                            self.provider_id,
                            {"signals": signals},
                        )
                    messages = await self._assistant_messages(page)
                    latest = messages[-1] if len(messages) > before_count else ""
                    if latest and latest != "Thinking":
                        if first_seen_at is None:
                            first_seen_at = now
                        if latest != last_text:
                            last_text = latest
                            stable_since = now
                        elif stable_since is not None and now - stable_since >= stable_window:
                            self.last_assistant_text = latest
                            self.last_conversation_url = page.url
                            yield {"type": "text_delta", "text": latest, "conversation_id": page.url}
                            return
                    elif now - start > self.first_event_timeout and first_seen_at is None:
                        raise ProviderTimeoutError(self.provider_id, "DeepSeek Web Chat did not produce an assistant message")
                    await page.wait_for_timeout(int(self.poll_interval * 1000))
            except BaseException:
                logger.warning("Stopping DeepSeek Web Chat after failed/cancelled stream", exc_info=True)
                try:
                    await self.cancel_active_generation("stream_cancelled")
                except Exception:
                    logger.debug("DeepSeek active-generation cancel hook failed", exc_info=True)
                raise

    async def cancel_active_generation(self, reason: str = "client_cancelled") -> dict:
        """Best-effort click of the provider Web Chat stop/cancel control."""
        result = {"supported": True, "cancelled": False, "reason": reason, "method": "dom_stop_button"}
        page = self._page
        if not page or page.is_closed():
            result["detail"] = "no_active_page"
            return result
        try:
            clicked = await page.evaluate(
                """() => {
                  const visible = (el) => {
                    const r = el.getBoundingClientRect();
                    const st = window.getComputedStyle(el);
                    return r.width > 0 && r.height > 0 && st.visibility !== 'hidden' && st.display !== 'none';
                  };
                  const patterns = [
                    /stop/i, /cancel/i, /interrupt/i, /abort/i,
                    /停止|中止|取消|终止|توقف|لغو/i
                  ];
                  const nodes = Array.from(document.querySelectorAll('button,[role="button"],.ant-btn'));
                  const candidates = nodes.map((el) => ({
                    el,
                    label: [
                      el.innerText || '',
                      el.getAttribute('aria-label') || '',
                      el.getAttribute('title') || '',
                      el.getAttribute('data-testid') || '',
                      el.className || ''
                    ].join(' ').trim()
                  })).filter(x => visible(x.el) && patterns.some(p => p.test(x.label)));
                  if (candidates.length) {
                    candidates[0].el.click();
                    return {clicked: true, label: candidates[0].label.slice(0, 160), candidates: candidates.length};
                  }
                  return {clicked: false, candidates: 0};
                }"""
            )
            escape_sent = False
            if not clicked or not clicked.get("clicked"):
                try:
                    await page.keyboard.press("Escape")
                    escape_sent = True
                except Exception:
                    pass
            await page.wait_for_timeout(250)
            result.update(clicked or {})
            result["escape_sent"] = escape_sent
            result["attempted"] = bool((clicked or {}).get("clicked")) or escape_sent
            # Escape is only an interruption attempt; do not treat it as proof
            # that the provider stopped upstream generation.
            result["cancelled"] = bool((clicked or {}).get("clicked"))
        except Exception as exc:
            result["error"] = str(exc)[:240]
        return result

    async def close(self) -> None:
        self._page = None
        self._context = None
        self._browser = None
        if self._pw:
            try:
                await self._pw.stop()
            except Exception:
                pass
            self._pw = None
