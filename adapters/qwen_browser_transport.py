import asyncio
import logging
import re
import time
from pathlib import Path
from typing import AsyncIterator, Optional

from playwright.async_api import async_playwright, BrowserContext, Page, Playwright

from core.providers import ProviderError, ProviderTimeoutError

logger = logging.getLogger(__name__)


class QwenBrowserControllerTransport:
    """Use Qwen's own frontend controller as a backend transport.

    This does not type/click the chat DOM. It calls the frontend controller that
    owns request construction, anti-bot integration, session lifecycle and SSE
    processing. Output is reconstructed incrementally from the controller's
    in-memory message state.
    """

    def __init__(
        self,
        provider_id: str,
        profile_dir: str,
        *,
        base_url: str = "https://chat.qwen.ai/",
        channel: str = "chrome",
        headless: bool = True,
        launch_timeout: float = 45.0,
        first_event_timeout: float = 30.0,
        idle_timeout: float = 45.0,
        total_timeout: float = 180.0,
        poll_interval: float = 0.08,
    ):
        self.provider_id = provider_id
        self.profile_dir = str(Path(profile_dir))
        self.base_url = base_url
        self.channel = channel
        self.headless = headless
        self.launch_timeout = launch_timeout
        self.first_event_timeout = first_event_timeout
        self.idle_timeout = idle_timeout
        self.total_timeout = total_timeout
        self.poll_interval = poll_interval
        self._pw: Optional[Playwright] = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None
        self._lock = asyncio.Lock()
        self.frontend_version: Optional[str] = None
        self.main_module_url: Optional[str] = None
        self.last_session_mode: str = "unknown"

    async def _ensure(self) -> Page:
        if self._page and not self._page.is_closed():
            return self._page
        Path(self.profile_dir).mkdir(parents=True, exist_ok=True)
        try:
            self._pw = await async_playwright().start()
            self._context = await self._pw.chromium.launch_persistent_context(
                self.profile_dir,
                channel=self.channel,
                headless=self.headless,
                args=["--disable-default-apps", "--no-first-run"],
                timeout=int(self.launch_timeout * 1000),
            )
            self._page = self._context.pages[0] if self._context.pages else await self._context.new_page()
            await self._page.goto(self.base_url, wait_until="domcontentloaded", timeout=int(self.launch_timeout * 1000))
            await self._page.wait_for_timeout(2500)
            await self._bootstrap_controller(self._page)
            return self._page
        except Exception as exc:
            await self._reset()
            raise ProviderError(
                "Qwen browser controller bootstrap failed",
                "browser_bootstrap_error",
                self.provider_id,
                {"exception": type(exc).__name__},
            ) from exc

    async def _bootstrap_controller(self, page: Page) -> None:
        discovery = await page.evaluate(
            r"""() => {
              const urls = [
                ...Array.from(document.scripts).map(s => s.src),
                ...performance.getEntriesByType('resource').map(e => e.name)
              ].filter(Boolean);
              const u = urls.find(x => /qwen-chat-fe\/[^/]+\/js\/main\.js(?:\?|$)/.test(x));
              return u || '';
            }"""
        )
        if not discovery:
            raise RuntimeError("Qwen frontend main module was not discovered")
        match = re.search(r"qwen-chat-fe/([^/]+)/js/main\.js", discovery)
        self.frontend_version = match.group(1) if match else None
        self.main_module_url = discovery
        await page.evaluate(
            """async (url) => {
              const m = await import(url);
              if (!m.i || typeof m.i.beforeSendMessage !== 'function')
                throw new Error('Qwen controller export not found');
              window.__mwbQwenController = m.i;
              window.__mwbQwenFeatureManager = m.n || null;
              window.__mwbQwenFeatureEnum = m.I || null;
              window.__mwbQwenSendError = null;
              return true;
            }""",
            discovery,
        )

    async def session_status(self) -> dict:
        page = await self._ensure()
        result = await page.evaluate(
            """async () => {
              try {
                const r = await fetch('/api/v1/auths/', {credentials:'include'});
                return {status:r.status, authenticated:r.ok};
              } catch (e) {
                return {status:0, authenticated:false};
              }
            }"""
        )
        self.last_session_mode = "authenticated" if result.get("authenticated") else "guest"
        return {"authenticated": bool(result.get("authenticated")), "http_status": int(result.get("status") or 0), "mode": self.last_session_mode}

    async def model_ids(self) -> list[str]:
        page = await self._ensure()
        result = await page.evaluate(
            """async () => {
              const r = await fetch('/api/v2/models/', {credentials:'include'});
              if (!r.ok) return {status:r.status, ids:[]};
              const j = await r.json();
              const rows = j?.data?.data || [];
              return {status:r.status, ids:rows.map(x=>x?.id).filter(Boolean)};
            }"""
        )
        if int(result.get("status") or 0) in (401, 403):
            raise ProviderError("Qwen model discovery requires session", "auth_required", self.provider_id)
        return [str(x) for x in result.get("ids", [])]

    async def health(self) -> bool:
        try:
            await self._ensure()
            await self.session_status()
            return True
        except Exception:
            return False

    async def _start_send(self, prompt: str, *, thinking: bool, search: bool) -> str:
        page = await self._ensure()
        result = await page.evaluate(
            """async ({prompt, thinking, search}) => {
              const x = window.__mwbQwenController;
              if (!x) throw new Error('controller_not_ready');
              const fm = window.__mwbQwenFeatureManager;
              const fe = window.__mwbQwenFeatureEnum;
              if (fm && fe) {
                const thinkingFeature = fe.Thinking || 'thinking';
                const searchFeature = fe.WebSearch || 'web_search';
                if (thinking) {
                  const r1 = fm.selectFeature(thinkingFeature);
                  if (r1 && r1.success === false) throw new Error('thinking_enable_failed');
                  const r2 = fm.setThinkingMode('Auto');
                  if (r2 && r2.success === false) throw new Error('thinking_mode_failed');
                } else {
                  const r1 = fm.deselectFeature(thinkingFeature);
                  if (r1 && r1.success === false) throw new Error('thinking_disable_failed');
                }
                if (search) {
                  const rs = fm.selectFeature(searchFeature);
                  if (rs && rs.success === false) throw new Error('search_enable_failed');
                } else {
                  const rs = fm.deselectFeature(searchFeature);
                  if (rs && rs.success === false) throw new Error('search_disable_failed');
                }
              }
              await x.openNewChat({hideToast:true, sendEventTrack:false});
              try {
                const feature = x.currentInputFeature;
              } catch (_) {}
              window.__mwbQwenSendError = null;
              Promise.resolve(x.beforeSendMessage({inputText:prompt}))
                .catch(e => { window.__mwbQwenSendError = String(e?.message || e || 'send_failed'); });
              return x.currentInstanceId || '';
            }""",
            {"prompt": prompt, "thinking": thinking, "search": search},
        )
        return str(result or "")

    async def _snapshot(self) -> dict:
        page = await self._ensure()
        return await page.evaluate(
            """() => {
              const x = window.__mwbQwenController;
              const s = x?.getPool?.().currentSession;
              if (!s) return {state:'missing', chat_id:'', answer:'', thinking:'', terminal:false, error:window.__mwbQwenSendError || null};
              const h = s.history || {};
              const ids = Array.isArray(h.currentResponseIds) ? h.currentResponseIds : [];
              let msg = null;
              for (let i=ids.length-1;i>=0;i--) {
                const candidate = h.messages?.[ids[i]];
                if (candidate?.role === 'assistant') { msg=candidate; break; }
              }
              if (!msg && h.currentId) {
                const candidate = h.messages?.[h.currentId];
                if (candidate?.role === 'assistant') msg=candidate;
              }
              let answer='', thinking='', answerStatus='', thinkingStatus='';
              for (const part of (msg?.content_list || [])) {
                if (part?.phase === 'answer') { answer = typeof part.content === 'string' ? part.content : answer; answerStatus=part.status || answerStatus; }
                else if (part?.phase === 'thinking_summary' || part?.phase === 'thinking') { thinking = typeof part.content === 'string' ? part.content : thinking; thinkingStatus=part.status || thinkingStatus; }
              }
              const terminal = !!msg && (msg.done === true || answerStatus === 'finished') && s.sessionState === 'ready';
              return {
                state: s.sessionState || '',
                chat_id: s.chatId || '',
                answer, thinking, answer_status:answerStatus, thinking_status:thinkingStatus,
                has_event: !!msg || s.sessionState !== 'ready',
                terminal,
                error: window.__mwbQwenSendError || null
              };
            }"""
        )

    async def stream_text(self, prompt: str, *, thinking: bool = True, search: bool = False) -> AsyncIterator[dict]:
        async with self._lock:
            started = time.monotonic()
            last_meaningful = started
            saw_event = False
            emitted = ""
            thinking_emitted = ""
            chat_id = ""
            await self._start_send(prompt, thinking=thinking, search=search)
            while True:
                now = time.monotonic()
                if now - started > self.total_timeout:
                    raise ProviderTimeoutError(self.provider_id, "Qwen total stream timeout")
                snap = await self._snapshot()
                chat_id = snap.get("chat_id") or chat_id
                if snap.get("error"):
                    raise ProviderError("Qwen controller send failed", "upstream_error", self.provider_id)
                if snap.get("has_event"):
                    if not saw_event:
                        saw_event = True
                        last_meaningful = now
                    elif snap.get("answer") != emitted or snap.get("thinking") != thinking_emitted:
                        last_meaningful = now
                elif now - started > self.first_event_timeout:
                    raise ProviderTimeoutError(self.provider_id, "Qwen first event timeout")

                full_thinking = snap.get("thinking") or ""
                if full_thinking.startswith(thinking_emitted) and len(full_thinking) > len(thinking_emitted):
                    delta = full_thinking[len(thinking_emitted):]
                    thinking_emitted = full_thinking
                    yield {"type":"reasoning_delta", "text":delta, "chat_id":chat_id}

                full = snap.get("answer") or ""
                if full.startswith(emitted) and len(full) > len(emitted):
                    delta = full[len(emitted):]
                    emitted = full
                    last_meaningful = now
                    yield {"type":"text_delta", "text":delta, "chat_id":chat_id}
                elif full and full != emitted:
                    # Unexpected non-monotonic state: do not replay potentially duplicated text.
                    raise ProviderError("Qwen reconstructed stream became non-monotonic", "protocol_error", self.provider_id)

                if saw_event and now - last_meaningful > self.idle_timeout and not snap.get("terminal"):
                    raise ProviderTimeoutError(self.provider_id, "Qwen meaningful idle timeout")
                if snap.get("terminal"):
                    yield {"type":"done", "text":"", "chat_id":chat_id}
                    return
                await asyncio.sleep(self.poll_interval)

    async def close(self) -> None:
        await self._reset()

    async def _reset(self) -> None:
        page, context, pw = self._page, self._context, self._pw
        self._page = None
        self._context = None
        self._pw = None
        try:
            if page and not page.is_closed():
                await page.close()
        except Exception:
            pass
        try:
            if context:
                await context.close()
        except Exception:
            pass
        try:
            if pw:
                await pw.stop()
        except Exception:
            pass
