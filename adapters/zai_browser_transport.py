import asyncio
import json
import logging
import re
import time
from typing import AsyncIterator, Optional

from playwright.async_api import Browser, BrowserContext, Page, Playwright, async_playwright

from core.commitment import Commitment, CommitmentTracker, annotate_error_details
from core.providers import ProviderError, ProviderTimeoutError
from core.model_liveness import classify_model_liveness
from core.visual_discovery import wait_for_upload_settled, capture_user_view, visible_page_state

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
        self.last_backend_features: dict = {}
        self.last_backend_features_original: dict = {}
        self.last_requested_model: Optional[str] = None
        self.last_backend_response_status: Optional[int] = None
        self.last_backend_response_content_type: Optional[str] = None
        self.backend_lifecycle: list[dict] = []
        self.last_liveness: dict = {}
        self.last_commitment_state: str = Commitment.NOT_SENT.value

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
                features = payload.get("features") if isinstance(payload, dict) else None
                if isinstance(features, dict):
                    self.last_backend_features_original = {
                        key: features.get(key)
                        for key in (
                            "enable_thinking",
                            "reasoning_effort",
                            "web_search",
                            "auto_web_search",
                        )
                    }
                else:
                    self.last_backend_features_original = {}
            except Exception:
                self.last_backend_request_model = None
                self.last_backend_features_original = {}
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
                snap = await page.evaluate(script, prompt)
                if snap.get("matched"):
                    snap["source"] = "history_store"
                    return snap
                visible = await page.evaluate(
                    """(prompt) => {
                      const path = location.pathname.split('/').filter(Boolean);
                      const chatId = path[0] === 'c' && path[1] ? path[1] : '';
                      if (!chatId) return {matched:false, source:'visible_dom', chatId:''};
                      const body = document.body?.innerText || '';
                      if (!body.includes(prompt)) return {matched:false, source:'visible_dom', chatId};
                      const nodes = Array.from(document.querySelectorAll('.chat-assistant, #response-content-container'));
                      const visible = nodes.filter((el) => {
                        const r = el.getBoundingClientRect(); const cs = getComputedStyle(el);
                        return r.width > 0 && r.height > 0 && cs.display !== 'none' && cs.visibility !== 'hidden';
                      });
                      const text = visible.length ? (visible[visible.length - 1].innerText || visible[visible.length - 1].textContent || '').trim() : '';
                      return {ready:true, matched:!!text, text, reasoning:'', done:false, phase:'visible', error:null, model:'', chatId, source:'visible_dom'};
                    }""", prompt
                )
                return visible
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
            for x in catalog:
                if upstream_model and upstream_model.replace("-flash", "") in (x.get("id") or ""):
                    match = x
                    break
        if not match:
            raise ProviderError(
                "Requested Z.ai model is not available in the current session",
                "invalid_model",
                self.provider_id,
                {"model": upstream_model, "catalog": [x.get("id") for x in catalog]},
            )
        display_name = str(match.get("name") or upstream_model)

        button = page.locator("button.modelSelectorButton").first
        try:
            await button.wait_for(state="visible", timeout=int(self.launch_timeout * 1000))
            current = (await button.inner_text()).strip()
            if current != display_name:
                state = (await button.get_attribute("data-state")) or ""
                expanded = (await button.get_attribute("aria-expanded")) or ""
                if state.lower() != "open" and expanded.lower() != "true":
                    try:
                        await button.click()
                    except Exception:
                        handle = await button.element_handle()
                        if handle is None:
                            raise
                        await page.evaluate("button => button.click()", handle)
                # Z.ai model options include descriptions after the display name
                # (for example: "GLM-5.3\nFlagship model..."). Playwright text
                # matching may normalize newlines, so select by the first visible
                # line of each button inside the open menu. This also prevents
                # GLM-5.3 from colliding with GLM-5.3-Flash.
                clicked = await page.evaluate(
                    """(displayName) => {
                        const isVisible = (el) => {
                            const r = el.getBoundingClientRect();
                            const cs = getComputedStyle(el);
                            return !!(r.width && r.height && cs.display !== 'none' && cs.visibility !== 'hidden');
                        };
                        const buttons = Array.from(document.querySelectorAll('button'));
                        const option = buttons.find((button) => {
                            if (button.classList.contains('modelSelectorButton')) return false;
                            if (!isVisible(button)) return false;
                            const text = (button.innerText || button.textContent || '').trim();
                            const firstLine = text.replaceAll(String.fromCharCode(13), String.fromCharCode(10)).split(String.fromCharCode(10))[0].trim();
                            return firstLine === displayName;
                        });
                        if (!option) return false;
                        option.click();
                        return true;
                    }""",
                    display_name,
                )
                if not clicked:
                    option = page.locator(
                        "button, [role=option], [role=menuitem], [role=button]"
                    ).filter(has_text=re.compile(re.escape(display_name), re.I)).first
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

    async def _submit_file_prompt_via_ui(self, page: Page, prompt: str) -> dict:
        composer = page.locator("#chat-input").first
        if await composer.count() == 0:
            composer = page.locator("textarea").first
        if await composer.count() == 0:
            raise ProviderError("Z.ai visible composer not found", "composer_not_found", self.provider_id)
        await composer.fill(prompt)
        actual = await composer.input_value()
        if actual.strip() != prompt.strip():
            raise ProviderError(
                "Z.ai composer verification failed", "composer_verification_failed", self.provider_id,
                {"expected_length": len(prompt), "actual_length": len(actual)},
            )
        send = page.locator("#send-message-button").first
        if await send.count() == 0:
            raise ProviderError("Z.ai visible send control not found", "send_button_unavailable", self.provider_id)

        ready_deadline = time.monotonic() + 20.0
        while time.monotonic() < ready_deadline:
            if await send.is_visible() and await send.is_enabled():
                break
            await page.wait_for_timeout(200)
        else:
            evidence = await capture_user_view(page, self.provider_id, "file-prompt-send-disabled")
            raise ProviderError(
                "Z.ai send control did not become enabled", "send_button_unavailable", self.provider_id,
                {"visual_evidence": evidence},
            )

        evidence = await capture_user_view(page, self.provider_id, "file-prompt-ready")
        before_url = page.url
        submit_deadline = time.monotonic() + 60.0
        rejected_for_upload = 0
        nonbusy_failures = 0
        while time.monotonic() < submit_deadline:
            await send.click(timeout=5000)
            transition_deadline = time.monotonic() + 2.0
            while time.monotonic() < transition_deadline:
                current = ""
                try:
                    current = await composer.input_value()
                except Exception:
                    current = ""
                if not current.strip() or page.url != before_url or self.last_backend_request_model:
                    return evidence
                await page.wait_for_timeout(150)

            state = await visible_page_state(page)
            if state.get("upload_busy"):
                rejected_for_upload += 1
                await capture_user_view(page, self.provider_id, "file-prompt-upload-busy")
                await page.wait_for_timeout(2000)
                continue
            nonbusy_failures += 1
            if nonbusy_failures <= 1:
                await page.wait_for_timeout(750)
                continue
            break

        failed = await capture_user_view(page, self.provider_id, "file-prompt-submit-unconfirmed")
        raise ProviderError(
            "Z.ai send click did not produce a visible/backend transition",
            "submit_not_confirmed", self.provider_id,
            {"visual_evidence": failed, "upload_rejections": rejected_for_upload},
        )

    async def stream_text(
        self,
        prompt: str,
        *,
        upstream_model: Optional[str] = None,
        thinking: bool = False,
        search: bool = False,
        file_paths: Optional[list[str]] = None,
    ) -> AsyncIterator[dict]:
        if not prompt.strip():
            raise ProviderError("Z.ai prompt is empty", "invalid_request", self.provider_id)

        async with self._lock:
            page = await self._ensure()
            await self._prepare_new_chat(page)
            await self._select_model(page, upstream_model)

            status = await self.session_status()
            if not status.get("authenticated"):
                raise ProviderError("Z.ai Web requires an authenticated browser session", "auth_required", self.provider_id)

            if file_paths:
                file_input = page.locator("input[type=file]").first
                if await file_input.count() == 0:
                    raise ProviderError("Z.ai file input not found", "upload_failed", self.provider_id)
                try:
                    await file_input.set_input_files(list(file_paths))
                    for file_path in file_paths:
                        file_name = str(file_path).replace("\\", "/").rsplit("/", 1)[-1]
                        lifecycle = await wait_for_upload_settled(
                            page, self.provider_id, file_name, timeout_seconds=60.0
                        )
                        if not lifecycle.get("ready"):
                            raise ProviderError(
                                "Z.ai file upload did not reach a user-visible ready state",
                                "upload_not_ready", self.provider_id,
                                {"file_name": file_name, "visual_evidence": lifecycle.get("trace", [])[-3:]},
                            )
                except Exception as exc:
                    raise ProviderError(
                        "Z.ai file upload failed", "upload_failed", self.provider_id,
                        {"exception": type(exc).__name__},
                    ) from exc

            self.last_requested_model = upstream_model
            # Evidence must reflect an observed backend request, not the requested
            # model. The request listener sets this only when it sees the payload.
            self.last_backend_request_model = None
            self.last_backend_features = {}
            self.last_backend_features_original = {}
            start = time.monotonic()
            first_deadline = start + self.first_event_timeout
            total_deadline = start + self.total_timeout
            last_meaningful = start
            emitted = ""
            reasoning_emitted = ""
            visible_dom_last_text = ""
            visible_dom_stable_since = None
            committed = False
            feature_route_installed = False
            feature_verified = False

            async def feature_route(route, req):
                try:
                    payload = json.loads(req.post_data or "{}")
                    if not isinstance(payload, dict):
                        raise ValueError("completion payload is not an object")
                    features = payload.get("features")
                    if not isinstance(features, dict):
                        features = {}
                        payload["features"] = features
                    features["enable_thinking"] = bool(thinking)
                    features["reasoning_effort"] = "max" if thinking else "low"
                    features["web_search"] = bool(search)
                    features["auto_web_search"] = bool(search)
                    await route.continue_(post_data=json.dumps(payload, ensure_ascii=False))
                    self.last_backend_features = {
                        key: features.get(key)
                        for key in (
                            "enable_thinking",
                            "reasoning_effort",
                            "web_search",
                            "auto_web_search",
                        )
                    }
                except Exception:
                    logger.exception("Z.ai feature payload rewrite failed")
                    await route.abort("failed")

            try:
                await page.route("**/api/chat/completions**", feature_route)
                await page.route("**/api/v2/chat/completions**", feature_route)
                feature_route_installed = True
                commitment = CommitmentTracker(f"{self.provider_id}:{time.time_ns()}")
                self.last_commitment_state = commitment.state.value
                commitment.advance(Commitment.MAYBE_SENT)
                self.last_commitment_state = commitment.state.value
                if file_paths:
                    self.last_visual_submit_evidence = await self._submit_file_prompt_via_ui(page, prompt)
                else:
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
                commitment.advance(Commitment.COMMITTED)
                self.last_commitment_state = commitment.state.value

                while True:
                    now = time.monotonic()
                    if now > total_deadline:
                        raise ProviderTimeoutError(self.provider_id, "Z.ai total timeout")

                    snap = await self._snapshot(page, prompt)
                    marker_seen = False
                    try:
                        marker_seen = bool(snap.get("text") and "KGWM_" in str(snap.get("text")))
                    except Exception:
                        marker_seen = False
                    signal = classify_model_liveness(
                        matched=bool(snap.get("matched")),
                        reasoning_len=len(snap.get("reasoning") or ""),
                        text_len=len(snap.get("text") or ""),
                        done=bool(snap.get("done")),
                        phase=str(snap.get("phase") or ""),
                        error=snap.get("error"),
                        marker_seen=marker_seen,
                        backend_request_seen=bool(self.last_backend_request_model),
                    )
                    self.last_liveness = {
                        "state": signal.state,
                        "reason": signal.reason,
                        "matched": signal.matched,
                        "reasoning_len": signal.reasoning_len,
                        "text_len": signal.text_len,
                        "done": signal.done,
                        "phase": signal.phase,
                        "marker_seen": signal.marker_seen,
                        "backend_request_seen": signal.backend_request_seen,
                    }
                    if self.last_backend_request_model and not feature_verified:
                        observed = dict(self.last_backend_features or {})
                        expected = {
                            "enable_thinking": bool(thinking),
                            "reasoning_effort": "max" if thinking else "low",
                            "web_search": bool(search),
                            "auto_web_search": bool(search),
                        }
                        if any(observed.get(key) != value for key, value in expected.items()):
                            raise ProviderError(
                                "Z.ai feature control verification failed",
                                "feature_control_failed",
                                self.provider_id,
                                {"expected": expected, "observed": observed},
                            )
                        feature_verified = True
                        logger.info("Z.ai backend request seen model=%s after %.1fs",
                                    self.last_backend_request_model, now - start)
                    if snap.get("matched"):
                        reasoning = snap.get("reasoning") or ""
                        if reasoning != reasoning_emitted:
                            if reasoning.startswith(reasoning_emitted):
                                reasoning_emitted = reasoning
                                last_meaningful = now
                            else:
                                reasoning_emitted = reasoning
                                last_meaningful = now

                        if not emitted and not reasoning_emitted and now > first_deadline and not snap.get("text"):
                            raise ProviderTimeoutError(self.provider_id, "Z.ai first-event timeout")
                        text = snap.get("text") or ""
                        if text and not emitted:
                            logger.info("Z.ai first text after %.1fs (backend_seen=%s)",
                                        now - start, bool(self.last_backend_request_model))
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

                        if snap.get("source") == "visible_dom" and text:
                            if text != visible_dom_last_text:
                                visible_dom_last_text = text
                                visible_dom_stable_since = now
                            elif visible_dom_stable_since is not None and now - visible_dom_stable_since >= 2.0:
                                if not feature_verified:
                                    raise ProviderError(
                                        "Z.ai visible completion stabilized without feature-control evidence",
                                        "feature_control_failed", self.provider_id,
                                        {"thinking": thinking, "search": search},
                                    )
                                if commitment.state != Commitment.TERMINAL:
                                    commitment.advance(Commitment.TERMINAL)
                                    self.last_commitment_state = commitment.state.value
                                return

                        if snap.get("done") and snap.get("phase") == "done":
                            if not feature_verified:
                                raise ProviderError(
                                    "Z.ai completion finished without feature-control evidence",
                                    "feature_control_failed",
                                    self.provider_id,
                                    {"thinking": thinking, "search": search},
                                )
                            if commitment.state != Commitment.TERMINAL:
                                commitment.advance(Commitment.TERMINAL)
                                self.last_commitment_state = commitment.state.value
                            return

                    if now - last_meaningful > self.idle_timeout:
                        raise ProviderTimeoutError(self.provider_id, "Z.ai meaningful idle timeout")
                    await asyncio.sleep(self.poll_interval)
            except BaseException as exc:
                if isinstance(exc, ProviderError):
                    exc.details.update(annotate_error_details(exc.details, self.last_commitment_state))
                if committed:
                    logger.warning("Stopping Z.ai Web Chat after failed/cancelled stream", exc_info=True)
                    try:
                        await self.cancel_active_generation("stream_cancelled")
                    except Exception:
                        logger.debug("Z.ai active-generation cancel hook failed", exc_info=True)
                raise
            finally:
                if feature_route_installed:
                    try:
                        await page.unroute("**/api/chat/completions**", feature_route)
                        await page.unroute("**/api/v2/chat/completions**", feature_route)
                    except Exception:
                        logger.debug("Z.ai feature route cleanup failed", exc_info=True)

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
