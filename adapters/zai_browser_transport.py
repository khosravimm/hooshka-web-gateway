import asyncio
import json
import logging
import re
import time
from typing import AsyncIterator, Optional

from playwright.async_api import Browser, BrowserContext, Page, Playwright, async_playwright

from core.providers import ProviderError, ProviderTimeoutError

logger = logging.getLogger(__name__)


class ZaiBrowserControllerTransport:
    """Use Z.ai's own frontend event/controller path as a backend transport.

    The transport does not type into or click the chat DOM. It connects to an
    already-running Chrome via CDP, creates a dedicated bridge tab, submits
    through the frontend's documented-in-runtime input:prompt:submit event, and
    reconstructs output from the frontend's in-memory history store.
    """

    def __init__(
        self,
        provider_id: str,
        *,
        cdp_url: str = "http://127.0.0.1:9223",
        base_url: str = "https://chat.z.ai/",
        launch_timeout: float = 30.0,
        first_event_timeout: float = 45.0,
        idle_timeout: float = 60.0,
        total_timeout: float = 180.0,
        poll_interval: float = 0.10,
    ):
        self.provider_id = provider_id
        self.cdp_url = cdp_url.rstrip("/")
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

        self.frontend_version: Optional[str] = None
        self.main_module_url: Optional[str] = None
        self.last_session_mode: str = "unknown"
        self.last_selected_model_label: Optional[str] = None
        self.last_backend_request_model: Optional[str] = None
        self.last_requested_model: Optional[str] = None
        self.last_backend_response_status: Optional[int] = None
        self.last_backend_response_content_type: Optional[str] = None
        self.backend_lifecycle: list[dict] = []

    def _record_backend_lifecycle(self, event: dict) -> None:
        self.backend_lifecycle.append(event)
        if len(self.backend_lifecycle) > 20:
            self.backend_lifecycle = self.backend_lifecycle[-20:]

    def _attach_safe_model_diagnostics(self, page: Page) -> None:
        if getattr(page, "_hwg_zai_model_diag", False):
            return
        setattr(page, "_hwg_zai_model_diag", True)

        def on_request(req):
            if "/api/v2/chat/completions" not in req.url and "/api/chat/completions" not in req.url:
                return
            try:
                payload = json.loads(req.post_data or "{}")
                model = payload.get("model") if isinstance(payload, dict) else None
                self.last_backend_request_model = str(model) if model else None
            except Exception:
                self.last_backend_request_model = None
            self._record_backend_lifecycle({
                "event": "request",
                "model": self.last_backend_request_model,
            })

        def on_response(resp):
            if "/api/v2/chat/completions" not in resp.url and "/api/chat/completions" not in resp.url:
                return
            self.last_backend_response_status = int(resp.status)
            self.last_backend_response_content_type = str(resp.headers.get("content-type") or "")[:120]
            self._record_backend_lifecycle({
                "event": "response",
                "status": self.last_backend_response_status,
                "content_type": self.last_backend_response_content_type,
            })

        def on_request_failed(req):
            if "/api/v2/chat/completions" not in req.url and "/api/chat/completions" not in req.url:
                return
            failure = req.failure
            self._record_backend_lifecycle({
                "event": "request_failed",
                "error": str(failure or "")[:160],
            })

        page.on("request", on_request)
        page.on("response", on_response)
        page.on("requestfailed", on_request_failed)

    async def _ensure(self) -> Page:
        if self._page and not self._page.is_closed():
            try:
                if await self._page.evaluate("() => location.hostname === 'chat.z.ai'"):
                    self._attach_safe_model_diagnostics(self._page)
                    await self._bootstrap_runtime(self._page)
                    return self._page
            except Exception:
                pass

        try:
            if not self._pw:
                self._pw = await async_playwright().start()
            self._browser = await self._pw.chromium.connect_over_cdp(
                self.cdp_url,
                timeout=int(self.launch_timeout * 1000),
            )
            contexts = self._browser.contexts
            if not contexts:
                raise RuntimeError("No browser context available on Z.ai CDP browser")
            self._context = contexts[0]
            self._page = await self._context.new_page()
            self._attach_safe_model_diagnostics(self._page)
            await self._page.goto(
                self.base_url,
                wait_until="domcontentloaded",
                timeout=int(self.launch_timeout * 1000),
            )
            await self._page.wait_for_timeout(2500)
            await self._bootstrap_runtime(self._page)
            return self._page
        except Exception as exc:
            await self._reset()
            raise ProviderError(
                "Z.ai browser controller bootstrap failed",
                "browser_bootstrap_error",
                self.provider_id,
                {"exception": type(exc).__name__, "message": str(exc)[:240]},
            ) from exc

    async def _discover_main_module(self, page: Page) -> str:
        deadline = time.monotonic() + self.launch_timeout
        while time.monotonic() < deadline:
            url = await page.evaluate(
                r"""() => {
                  const urls = [
                    ...Array.from(document.scripts).map(s => s.src),
                    ...performance.getEntriesByType('resource').map(e => e.name)
                  ].filter(Boolean);
                  return urls.find(x => /z-ai\/frontend\/prod-fe-[^/]+\/assets\/index-[^/]+\.js(?:\?|$)/.test(x)) || '';
                }"""
            )
            if url:
                return str(url)
            await page.wait_for_timeout(400)
        raise RuntimeError("Z.ai frontend main module was not discovered")

    async def _bootstrap_runtime(self, page: Page) -> None:
        # Keep bootstrap idempotent; avoid relying on minified export names.
        try:
            is_ready = bool(
                await page.evaluate(
                    "() => !!window.__mwbZaiHistoryStore && !!window.__mwbZaiConfigStore"
                )
            )
        except Exception:
            is_ready = False
        if is_ready:
            return

        discovery = await self._discover_main_module(page)
        self.main_module_url = discovery
        match = re.search(r"/frontend/(prod-fe-[^/]+)/assets/", discovery)
        self.frontend_version = match.group(1) if match else None

        await page.evaluate(
            """async (url) => {
              const m = await import(url);
              const stores = Object.values(m).filter(v => v && typeof v === 'object' && typeof v.subscribe === 'function');
              const read = (store) => {
                let value;
                const unsub = store.subscribe(v => { value = v; });
                if (typeof unsub === 'function') unsub();
                return value;
              };
              const history = stores.find(store => {
                try {
                  const v = read(store);
                  return v && typeof v === 'object' && v.messages && typeof v.messages === 'object'
                    && Object.prototype.hasOwnProperty.call(v, 'currentId');
                } catch (_) { return false; }
              });
              const config = stores.find(store => {
                try {
                  const v = read(store);
                  return v && typeof v === 'object'
                    && Object.prototype.hasOwnProperty.call(v, 'completion_version')
                    && Object.prototype.hasOwnProperty.call(v, 'features');
                } catch (_) { return false; }
              });
              if (!history || !config) throw new Error('Z.ai runtime stores not found');
              window.__mwbZaiHistoryStore = history;
              window.__mwbZaiConfigStore = config;
              window.__mwbZaiModule = m;
              return true;
            }""",
            discovery,
        )

    async def _prepare_new_chat(self, page: Page) -> None:
        if page.url.rstrip("/") != self.base_url.rstrip("/"):
            await page.goto(
                self.base_url,
                wait_until="domcontentloaded",
                timeout=int(self.launch_timeout * 1000),
            )
            await page.wait_for_timeout(1800)
        else:
            # Reloading root ensures a clean stateless request without touching
            # the user's existing conversation tab.
            await page.reload(wait_until="domcontentloaded", timeout=int(self.launch_timeout * 1000))
            await page.wait_for_timeout(1800)
        await self._bootstrap_runtime(page)

    async def session_status(self) -> dict:
        page = await self._ensure()
        result = await page.evaluate(
            """async () => {
              const token = localStorage.getItem('token') || '';
              const headers = {
                'Accept':'application/json',
                'Content-Type':'application/json',
                'Accept-Language': navigator.language || 'en-US'
              };
              if (token) headers.authorization = 'Bearer ' + token;
              try {
                const r = await fetch('/api/models', {method:'GET', headers, credentials:'include'});
                return {status:r.status, authenticated:!!token && r.ok};
              } catch (_) {
                return {status:0, authenticated:false};
              }
            }"""
        )
        self.last_session_mode = "authenticated" if result.get("authenticated") else "guest"
        return {
            "authenticated": bool(result.get("authenticated")),
            "http_status": int(result.get("status") or 0),
            "mode": self.last_session_mode,
        }

    async def model_catalog(self) -> list[dict]:
        page = await self._ensure()
        result = await page.evaluate(
            """async () => {
              const token = localStorage.getItem('token') || '';
              const headers = {
                'Accept':'application/json',
                'Content-Type':'application/json',
                'Accept-Language': navigator.language || 'en-US'
              };
              if (token) headers.authorization = 'Bearer ' + token;
              const r = await fetch('/api/models', {method:'GET', headers, credentials:'include'});
              let j = null;
              try { j = await r.json(); } catch (_) {}
              const rows = Array.isArray(j) ? j : (j?.data || []);
              const models = Array.isArray(rows) ? rows.map(x => ({
                id: x?.id || '',
                name: x?.name || x?.display_name || x?.id || ''
              })).filter(x => x.id) : [];
              return {status:r.status, models};
            }"""
        )
        status = int(result.get("status") or 0)
        if status in (401, 403):
            raise ProviderError("Z.ai session is not authenticated", "auth_required", self.provider_id)
        if status != 200:
            raise ProviderError(
                "Z.ai model discovery failed",
                "upstream_http_error",
                self.provider_id,
                {"http_status": status},
            )
        return [
            {"id": str(x.get("id")), "name": str(x.get("name") or x.get("id"))}
            for x in result.get("models", [])
            if isinstance(x, dict) and x.get("id")
        ]

    async def model_ids(self) -> list[str]:
        return [x["id"] for x in await self.model_catalog()]

    async def health(self) -> bool:
        try:
            ids = await self.model_ids()
            return bool(ids)
        except Exception:
            return False

    async def _snapshot(self, page: Page, prompt: str) -> dict:
        script = """(prompt) => {
              const store = window.__mwbZaiHistoryStore;
              if (!store) return {ready:false};
              let h;
              const unsub = store.subscribe(v => { h = v; });
              if (typeof unsub === 'function') unsub();
              if (!h || !h.messages) return {ready:false};

              let id = h.currentId;
              let assistant = null;
              let user = null;
              for (let i=0; i<8 && id; i++) {
                const msg = h.messages[id];
                if (!msg) break;
                if (!assistant && msg.role === 'assistant') assistant = msg;
                if (msg.role === 'user') {
                  user = msg;
                  if ((msg.content || '') === prompt) break;
                }
                id = msg.parentId;
              }
              const matched = !!user && (user.content || '') === prompt && !!assistant;
              const blocks = Array.isArray(assistant?.content_blocks) ? assistant.content_blocks : [];
              const text = blocks.filter(b => b?.type === 'text' && typeof b.content === 'string').map(b => b.content).join('');
              const reasoning = blocks.filter(b => b?.type === 'reasoning' && typeof b.content === 'string').map(b => b.content).join('');
              const error = assistant?.error || null;
              const path = location.pathname.split('/').filter(Boolean);
              const chatId = path[0] === 'c' && path[1] ? path[1] : '';
              return {
                ready:true,
                matched,
                currentId:h.currentId || '',
                assistantId:assistant?.id || '',
                text,
                reasoning,
                done:assistant?.done === true,
                phase:assistant?.phase || '',
                error,
                model:assistant?.model || '',
                chatId
              };
            }"""
        last_exc = None
        for attempt in range(4):
            try:
                runtime_ready = bool(await page.evaluate("() => !!window.__mwbZaiHistoryStore"))
                if not runtime_ready:
                    try:
                        await page.wait_for_load_state("domcontentloaded", timeout=int(self.launch_timeout * 1000))
                    except Exception:
                        pass
                    await self._bootstrap_runtime(page)
                return await page.evaluate(script, prompt)
            except Exception as exc:
                last_exc = exc
                msg = str(exc).lower()
                transient = "execution context was destroyed" in msg or "navigation" in msg
                if not transient or attempt == 3:
                    raise
                await page.wait_for_timeout(250)
        raise last_exc or RuntimeError("Z.ai snapshot failed")

    async def _select_model(self, page: Page, upstream_model: Optional[str]) -> None:
        if not upstream_model:
            return
        catalog = await self.model_catalog()
        match = next((x for x in catalog if x.get("id") == upstream_model), None)
        if not match:
            raise ProviderError(
                "Requested Z.ai model is not available in the current session",
                "invalid_model",
                self.provider_id,
                {"model": upstream_model},
            )
        display_name = str(match.get("name") or upstream_model)

        button = page.locator("button.modelSelectorButton").first
        try:
            await button.wait_for(state="visible", timeout=int(self.launch_timeout * 1000))
            current = (await button.inner_text()).strip()
            if current != display_name:
                await button.click()
                option = page.locator(
                    "button, [role=option], [role=menuitem], [role=button]"
                ).filter(has_text=re.compile(f"^{re.escape(display_name)}$", re.I)).first
                await option.wait_for(state="visible", timeout=int(self.launch_timeout * 1000))
                await option.click()
                await page.wait_for_timeout(900)
            selected = (await page.locator("button.modelSelectorButton").first.inner_text()).strip()
        except Exception as exc:
            raise ProviderError(
                "Z.ai explicit model selection failed",
                "model_select_error",
                self.provider_id,
                {"model": upstream_model, "exception": type(exc).__name__},
            ) from exc
        self.last_selected_model_label = selected
        if selected != display_name:
            raise ProviderError(
                "Z.ai explicit model selection was not retained",
                "model_select_error",
                self.provider_id,
                {"model": upstream_model, "selected": selected[:80]},
            )
        if "Flash" in selected and "Flash" not in display_name:
            raise ProviderError(
                "Z.ai explicit model selection resolved to Flash variant",
                "model_select_error",
                self.provider_id,
                {"model": upstream_model, "selected": selected[:80]},
            )

    async def stream_text(self, prompt: str, *, upstream_model: Optional[str] = None) -> AsyncIterator[dict]:
        if not prompt.strip():
            raise ProviderError("Z.ai prompt is empty", "invalid_request", self.provider_id)

        async with self._lock:
            page = await self._ensure()
            await self._prepare_new_chat(page)
            await self._select_model(page, upstream_model)

            status = await self.session_status()
            if not status.get("authenticated"):
                raise ProviderError("Z.ai Web requires an authenticated browser session", "auth_required", self.provider_id)

            self.last_requested_model = upstream_model
            # Evidence must reflect an observed backend request, not the requested
            # model. The request listener sets this only when it sees the payload.
            self.last_backend_request_model = None
            start = time.monotonic()
            first_deadline = start + self.first_event_timeout
            total_deadline = start + self.total_timeout
            last_meaningful = start
            emitted = ""
            committed = False

            try:
                await page.evaluate(
                    """(prompt) => {
                      window.postMessage(
                        {type:'input:prompt:submit', text:prompt},
                        window.origin
                      );
                    }""",
                    prompt,
                )
                committed = True

                while True:
                    now = time.monotonic()
                    if now > total_deadline:
                        raise ProviderTimeoutError(self.provider_id, "Z.ai total timeout")

                    snap = await self._snapshot(page, prompt)
                    if snap.get("matched"):
                        if not emitted and now > first_deadline and not snap.get("text"):
                            raise ProviderTimeoutError(self.provider_id, "Z.ai first-event timeout")
                        text = snap.get("text") or ""
                        if text != emitted:
                            if not text.startswith(emitted):
                                raise ProviderError(
                                    "Z.ai reconstructed stream regressed",
                                    "protocol_error",
                                    self.provider_id,
                                )
                            delta = text[len(emitted):]
                            emitted = text
                            last_meaningful = now
                            if delta:
                                yield {
                                    "type": "text_delta",
                                    "text": delta,
                                    "chat_id": snap.get("chatId") or "",
                                    "model": snap.get("model") or self.last_backend_request_model or upstream_model or "",
                                }

                        error = snap.get("error")
                        if error:
                            message = str(error)
                            lower = message.lower()
                            code = "captcha_required" if "verif" in lower or "captcha" in lower else "upstream_error"
                            raise ProviderError(
                                "Z.ai frontend reported an upstream error",
                                code,
                                self.provider_id,
                                {"message": message[:240]},
                            )

                        if snap.get("done") and snap.get("phase") == "done":
                            return

                    if now - last_meaningful > self.idle_timeout:
                        raise ProviderTimeoutError(self.provider_id, "Z.ai meaningful idle timeout")
                    await asyncio.sleep(self.poll_interval)
            except Exception:
                # No replay once submission has crossed the commitment boundary.
                if committed:
                    raise
                raise

    async def _reset(self) -> None:
        if self._page and not self._page.is_closed():
            try:
                await self._page.close()
            except Exception:
                pass
        self._page = None
        self._context = None
        self._browser = None
        if self._pw:
            try:
                await self._pw.stop()
            except Exception:
                pass
        self._pw = None

    async def close(self) -> None:
        await self._reset()
