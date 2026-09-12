import asyncio
import json
import logging
import re
import time
from pathlib import Path
from typing import AsyncIterator, Optional

from playwright.async_api import async_playwright, Browser, BrowserContext, Page, Playwright

from core.providers import ProviderError, ProviderTimeoutError
from core.provider_risk import detect_provider_risk

logger = logging.getLogger(__name__)


_TRANSIENT_NAVIGATION_MARKERS = (
    "Execution context was destroyed",
    "Cannot find context with specified id",
    "Target page, context or browser has been closed",
)


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
        cdp_url: str | None = None,
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
        self.cdp_url = cdp_url
        self.launch_timeout = launch_timeout
        self.first_event_timeout = first_event_timeout
        self.idle_timeout = idle_timeout
        self.total_timeout = total_timeout
        self.poll_interval = poll_interval
        self._pw: Optional[Playwright] = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._owns_context = False
        self._page: Optional[Page] = None
        self._lock = asyncio.Lock()
        self.frontend_version: Optional[str] = None
        self.main_module_url: Optional[str] = None
        self.last_session_mode: str = "unknown"
        self._network_events: list[dict] = []
        self.last_selected_models: list[str] = []
        self.last_backend_request_model: Optional[str] = None

    def _record_network_event(self, event: dict) -> None:
        self._network_events.append(event)
        if len(self._network_events) > 20:
            self._network_events = self._network_events[-20:]

    def _attach_network_diagnostics(self, page: Page) -> None:
        if getattr(page, "_mwb_qwen_netdiag", False):
            return
        setattr(page, "_mwb_qwen_netdiag", True)

        def on_request(req):
            if "/api/v2/chats/new" in req.url or "/api/v2/chat/completions" in req.url:
                event = {"kind": "request", "url": req.url.split("?")[0][-80:]}
                if "/api/v2/chat/completions" in req.url:
                    try:
                        payload = json.loads(req.post_data or "{}")
                        model = payload.get("model") if isinstance(payload, dict) else None
                        if not model and isinstance(payload, dict):
                            messages = payload.get("messages") or []
                            if messages and isinstance(messages[0], dict):
                                models = messages[0].get("models") or []
                                model = models[0] if models else None
                        self.last_backend_request_model = str(model) if model else None
                        event["model"] = self.last_backend_request_model
                    except Exception:
                        self.last_backend_request_model = None
                self._record_network_event(event)

        def on_response(resp):
            if "/api/v2/chats/new" in resp.url or "/api/v2/chat/completions" in resp.url:
                self._record_network_event(
                    {
                        "kind": "response",
                        "url": resp.url.split("?")[0][-80:],
                        "status": resp.status,
                        "content_type": resp.headers.get("content-type", "")[:80],
                    }
                )

        page.on("request", on_request)
        page.on("response", on_response)

    @staticmethod
    def _is_transient_navigation_error(exc: Exception) -> bool:
        return any(marker in str(exc) for marker in _TRANSIENT_NAVIGATION_MARKERS)

    async def _controller_ready(self, page: Page) -> bool:
        try:
            return bool(
                await page.evaluate(
                    """() => typeof window.__mwbQwenController?.beforeSendMessage === 'function'"""
                )
            )
        except Exception:
            return False

    async def _ensure(self) -> Page:
        if self._page and not self._page.is_closed():
            if await self._controller_ready(self._page):
                return self._page
            try:
                await self._bootstrap_controller(self._page)
                return self._page
            except Exception as exc:
                if not self._is_transient_navigation_error(exc):
                    raise
                await self._reset()

        Path(self.profile_dir).mkdir(parents=True, exist_ok=True)
        try:
            self._pw = await async_playwright().start()
            if self.cdp_url:
                self._browser = await self._pw.chromium.connect_over_cdp(
                    self.cdp_url,
                    timeout=int(self.launch_timeout * 1000),
                )
                self._context = self._browser.contexts[0] if self._browser.contexts else await self._browser.new_context()
                self._owns_context = False
                pages = [p for p in self._context.pages if "chat.qwen.ai" in (p.url or "")]
                self._page = pages[0] if pages else (self._context.pages[0] if self._context.pages else await self._context.new_page())
            else:
                self._context = await self._pw.chromium.launch_persistent_context(
                    self.profile_dir,
                    channel=self.channel,
                    headless=self.headless,
                    args=[
                        "--disable-default-apps",
                        "--disable-dev-shm-usage",
                        "--disable-gpu",
                        "--no-first-run",
                    ],
                    timeout=int(self.launch_timeout * 1000),
                )
                self._owns_context = True
                self._page = self._context.pages[0] if self._context.pages else await self._context.new_page()
            self._attach_network_diagnostics(self._page)
            await self._page.goto(
                self.base_url,
                wait_until="domcontentloaded",
                timeout=int(self.launch_timeout * 1000),
            )
            await self._page.wait_for_timeout(2500)
            await self._bootstrap_controller(self._page)
            return self._page
        except Exception as exc:
            await self._reset()
            raise ProviderError(
                "Qwen browser controller bootstrap failed",
                "browser_bootstrap_error",
                self.provider_id,
                {"exception": type(exc).__name__, "message": str(exc)[:240]},
            ) from exc

    async def _discover_main_module(self, page: Page) -> str:
        deadline = time.monotonic() + self.launch_timeout
        while time.monotonic() < deadline:
            try:
                discovery = await page.evaluate(
                    r"""() => {
                      const urls = [
                        ...Array.from(document.scripts).map(s => s.src),
                        ...performance.getEntriesByType('resource').map(e => e.name)
                      ].filter(Boolean);
                      return urls.find(x => /qwen-chat-fe\/[^/]+\/js\/main\.js(?:\?|$)/.test(x)) || '';
                    }"""
                )
                if discovery:
                    return str(discovery)
            except Exception as exc:
                if not self._is_transient_navigation_error(exc):
                    raise
            await page.wait_for_timeout(500)
        raise RuntimeError("Qwen frontend main module was not discovered")

    async def _bootstrap_controller(self, page: Page) -> None:
        discovery = await self._discover_main_module(page)
        match = re.search(r"qwen-chat-fe/([^/]+)/js/main\.js", discovery)
        self.frontend_version = match.group(1) if match else None
        self.main_module_url = discovery

        last_exc: Exception | None = None
        for attempt in range(3):
            try:
                await page.evaluate(
                    """async (url) => {
                      const m = await import(url);
                      if (!m.i || typeof m.i.beforeSendMessage !== 'function') {
                        throw new Error('Qwen controller export not found');
                      }
                      window.__mwbQwenController = m.i;
                      window.__mwbQwenFeatureManager = m.n || null;
                      window.__mwbQwenFeatureEnum = m.I || null;
                      window.__mwbQwenChatStore = Object.values(m).find(v => {
                        try {
                          const s = v?.getState?.();
                          return s && typeof s.setCurrentInputFeature === 'function' && typeof s.setCurrentInputSubType === 'function';
                        } catch (_) { return false; }
                      }) || null;
                      window.__mwbQwenRuntimeStore = Object.values(m).find(v => {
                        try {
                          const s = v?.getState?.();
                          return s && typeof s.setThinkingMode === 'function' && typeof s.setResearchMode === 'function';
                        } catch (_) { return false; }
                      }) || null;
                      window.__mwbQwenSendError = null;
                      return true;
                    }""",
                    discovery,
                )
                return
            except Exception as exc:
                last_exc = exc
                if attempt == 2 or not self._is_transient_navigation_error(exc):
                    break
                await page.wait_for_timeout(350 * (attempt + 1))
        if last_exc:
            raise last_exc

    async def _session_status_unlocked(self) -> dict:
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
        return {
            "authenticated": bool(result.get("authenticated")),
            "http_status": int(result.get("status") or 0),
            "mode": self.last_session_mode,
        }

    async def session_status(self) -> dict:
        async with self._lock:
            return await self._session_status_unlocked()

    async def model_ids(self) -> list[str]:
        async with self._lock:
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
            async with self._lock:
                await self._ensure()
                await self._session_status_unlocked()
            return True
        except Exception:
            return False

    async def _open_new_chat(self, page: Page) -> None:
        await page.evaluate(
            """async () => {
              const x = window.__mwbQwenController;
              if (!x) throw new Error('controller_not_ready');
              await x.openNewChat({hideToast:true, sendEventTrack:false});
              return true;
            }"""
        )

    async def _apply_features_and_send(self, page: Page, prompt: str, *, thinking: Optional[bool], search: bool, upstream_model: Optional[str] = None) -> str:
        return str(
            await page.evaluate(
                """async ({prompt, thinking, search, upstreamModel}) => {
                  const x = window.__mwbQwenController;
                  if (!x) throw new Error('controller_not_ready');
                  await x.openNewChat({hideToast:true, sendEventTrack:false});
                  const fm = window.__mwbQwenFeatureManager;
                  const fe = window.__mwbQwenFeatureEnum;
                  if (upstreamModel && fm?.setSingleModel) {
                    const mr = fm.setSingleModel(upstreamModel);
                    if (mr && mr.success === false) throw new Error('model_select_failed:' + (mr.message || upstreamModel));
                    if (fm.refreshModelDependentState) await fm.refreshModelDependentState();
                  }
                  const chatStore = window.__mwbQwenChatStore?.getState?.();
                  const runtimeStore = window.__mwbQwenRuntimeStore?.getState?.();
                  if (fm && fe) {
                    const thinkingFeature = fe.Thinking || 'thinking';
                    const searchFeature = fe.WebSearch || 'search';
                    const supportedThinkingModes = fm.getSupportedThinkingModes?.() || [];
                    if (thinking === true) {
                      const requestedThinkingMode =
                        supportedThinkingModes.includes('Auto') ? 'Auto' :
                        supportedThinkingModes.includes('Thinking') ? 'Thinking' :
                        null;
                      if (!requestedThinkingMode) throw new Error('thinking_unsupported');
                      const r1 = fm.selectFeature(thinkingFeature);
                      if (r1 && r1.success === false) throw new Error('thinking_enable_failed');
                      const r2 = fm.setThinkingMode(requestedThinkingMode);
                      if (r2 && r2.success === false) throw new Error('thinking_mode_failed');
                      if (runtimeStore?.setThinkingMode) runtimeStore.setThinkingMode(requestedThinkingMode);
                    } else if (thinking === false) {
                      if (supportedThinkingModes.includes('Fast')) {
                        const r1 = fm.selectFeature(thinkingFeature);
                        if (r1 && r1.success === false) throw new Error('thinking_fast_feature_failed');
                        const r2 = fm.setThinkingMode('Fast');
                        if (r2 && r2.success === false) throw new Error('thinking_mode_fast_failed');
                        if (runtimeStore?.setThinkingMode) runtimeStore.setThinkingMode('Fast');
                      } else {
                        const r1 = fm.deselectFeature(thinkingFeature);
                        if (r1 && r1.success === false) throw new Error('thinking_disable_failed');
                      }
                    }
                    if (search) {
                      const rs = fm.selectFeature(searchFeature);
                      if (rs && rs.success === false) throw new Error('search_enable_failed');
                      if (chatStore?.setCurrentInputFeature) chatStore.setCurrentInputFeature(searchFeature);
                      if (chatStore?.setCurrentInputSubType) chatStore.setCurrentInputSubType(searchFeature);
                      if (runtimeStore?.setSearchEnabled) runtimeStore.setSearchEnabled(true);
                    } else {
                      const rs = fm.deselectFeature(searchFeature);
                      if (rs && rs.success === false) throw new Error('search_disable_failed');
                      if (chatStore?.setCurrentInputFeature) chatStore.setCurrentInputFeature(fe.Txt2Txt || 't2t');
                      if (chatStore?.setCurrentInputSubType) chatStore.setCurrentInputSubType(fe.Txt2Txt || 't2t');
                      if (runtimeStore?.setSearchEnabled) runtimeStore.setSearchEnabled(false);
                    }
                    if (runtimeStore?.setResearchMode) runtimeStore.setResearchMode('normal');
                    if (typeof x.setChatOptions === 'function') {
                      x.setChatOptions({
                        currentInputFeature: {
                          selectedFeatures: [...(fm.currentSelection?.selectedFeatures || [])],
                          selectedModels: [...(fm.currentSelection?.selectedModels || [])],
                          uploadedFileTypes: [...(fm.currentSelection?.uploadedFileTypes || [])],
                          thinkingMode: fm.currentSelection?.thinkingMode || 'Auto'
                        }
                      });
                    }
                  }
                  window.__mwbQwenSendError = null;
                  window.__mwbQwenSelectedModels = [...(fm?.currentSelection?.selectedModels || [])];
                  await x.beforeSendMessage({inputText:prompt});
                  return x.currentInstanceId || '';
                }""",
                {"prompt": prompt, "thinking": thinking, "search": search, "upstreamModel": upstream_model},
            )
            or ""
        )

    async def _start_send(self, prompt: str, *, thinking: Optional[bool], search: bool, upstream_model: Optional[str] = None) -> str:
        page = await self._ensure()
        for attempt in range(2):
            try:
                await self._session_status_unlocked()
                self.last_backend_request_model = None
                result = await self._apply_features_and_send(page, prompt, thinking=thinking, search=search, upstream_model=upstream_model)
                self.last_selected_models = await page.evaluate(
                    "() => [...(window.__mwbQwenFeatureManager?.getSelectedModels?.() || window.__mwbQwenFeatureManager?.currentSelection?.selectedModels || [])].map(x => typeof x === 'string' ? x : x?.id).filter(Boolean)"
                )
                return result
            except Exception as exc:
                message = str(exc)
                if "thinking_unsupported" in message:
                    raise ProviderError(
                        "Qwen model does not support the requested thinking mode",
                        "unsupported_feature",
                        self.provider_id,
                        {"feature": "thinking", "upstream_model": upstream_model},
                    ) from exc
                if "model_select_failed" in message:
                    raise ProviderError(
                        "Qwen explicit model selection failed",
                        "invalid_model",
                        self.provider_id,
                        {"upstream_model": upstream_model},
                    ) from exc
                if "search_enable_failed" in message or "search_disable_failed" in message:
                    raise ProviderError(
                        "Qwen search feature state change failed",
                        "unsupported_feature",
                        self.provider_id,
                        {"feature": "search", "upstream_model": upstream_model},
                    ) from exc
                if not self._is_transient_navigation_error(exc) or attempt == 1:
                    raise
                await self._reset()
                page = await self._ensure()
        raise RuntimeError("Qwen send did not start")

    async def _snapshot(self, prompt: str) -> dict:
        page = await self._ensure()
        script = """(prompt) => {
          const x = window.__mwbQwenController;
          const s = x?.getPool?.().currentSession;
          if (!s) return {state:'missing', chat_id:'', answer:'', thinking:'', terminal:false, error:window.__mwbQwenSendError || null};
          const h = s.history || {};
          let msg = null;
          let matched = false;
          let id = h.currentId;
          for (let i=0; i<16 && id; i++) {
            const candidate = h.messages?.[id];
            if (!candidate) break;
            if (!msg && candidate?.role === 'assistant') msg = candidate;
            if (candidate?.role === 'user' && (candidate?.content || '') === prompt) {
              matched = !!msg;
              break;
            }
            id = candidate?.parentId;
          }
          if (!matched) {
            const rows = Object.values(h.messages || {});
            const user = rows.find(v => v?.role === 'user' && (v?.content || '') === prompt);
            if (user) {
              const ids = Array.isArray(user?.childrenIds) ? user.childrenIds : [];
              for (const childId of ids) {
                const candidate = h.messages?.[childId];
                if (candidate?.role === 'assistant') { msg = candidate; matched = true; break; }
              }
            }
          }
          let answer='', thinking='', answerStatus='', thinkingStatus='';
          for (const part of (msg?.content_list || [])) {
            if (part?.phase === 'answer') { answer = typeof part.content === 'string' ? part.content : answer; answerStatus=part.status || answerStatus; }
            else if (part?.phase === 'thinking_summary' || part?.phase === 'thinking') { thinking = typeof part.content === 'string' ? part.content : thinking; thinkingStatus=part.status || thinkingStatus; }
          }
          if (!answer && typeof msg?.content === 'string') answer = msg.content;
          const terminal = matched && !!msg && (msg.done === true || answerStatus === 'finished') && s.sessionState === 'ready';
          const rows = Object.values(h.messages || {});
          const debug = {
            current_id: h.currentId || '',
            response_ids: Array.isArray(h.currentResponseIds) ? h.currentResponseIds.length : 0,
            message_count: rows.length,
            roles: rows.slice(-12).map(v => v?.role || ''),
            current_role: h.messages?.[h.currentId]?.role || '',
            assistant_done: msg?.done === true,
            assistant_phase: msg?.phase || '',
            assistant_status: msg?.status || '',
            assistant_keys: msg ? Object.keys(msg).sort() : [],
            assistant_error_type: typeof msg?.error,
            assistant_error_present: !!msg?.error,
            assistant_error_keys: msg?.error && typeof msg.error === 'object' ? Object.keys(msg.error).sort() : [],
            assistant_error_code: msg?.error?.code ?? msg?.error?.status ?? msg?.error?.errorCode ?? '',
            assistant_error_message: typeof msg?.error?.message === 'string' ? msg.error.message.slice(0, 240) : (typeof msg?.error?.errorMessage === 'string' ? msg.error.errorMessage.slice(0, 240) : ''),
            assistant_content_type: typeof msg?.content,
            assistant_content_len: typeof msg?.content === 'string' ? msg.content.length : 0,
            part_meta: (msg?.content_list || []).map(p => ({
              phase: p?.phase || '',
              status: p?.status || '',
              content_type: typeof p?.content,
              content_len: typeof p?.content === 'string' ? p.content.length : 0
            }))
          };
          const bodyText = (document.body?.innerText || '');
          const bodyLower = bodyText.toLowerCase();
          const riskPhrases = [
            'you have reached the daily usage limit',
            'daily usage limit',
            'usage limit',
            'quota',
            'high demand',
            'too many requests',
            'rate limit',
            'please wait',
            'please drag the slider below to complete the verification',
            'please slide to verify',
            'complete the verification to ensure normal access',
            'drag the slider',
            'slide to verify'
          ];
          const visibleRiskText = riskPhrases.some(x => bodyLower.includes(x)) ? bodyText.slice(-1600) : '';
          return {
            state: s.sessionState || '',
            chat_id: s.chatId || '',
            answer, thinking, answer_status:answerStatus, thinking_status:thinkingStatus,
            visible_risk_text: visibleRiskText,
            matched,
            has_event: matched && !!msg,
            terminal,
            debug,
            error: window.__mwbQwenSendError || null
          };
        }"""
        for attempt in range(3):
            try:
                return await page.evaluate(script, prompt)
            except Exception as exc:
                if not self._is_transient_navigation_error(exc) or attempt == 2:
                    raise
                await page.wait_for_timeout(150)
        raise RuntimeError("unreachable")

    async def stream_text(self, prompt: str, *, thinking: Optional[bool] = None, search: bool = False, upstream_model: Optional[str] = None) -> AsyncIterator[dict]:
        async with self._lock:
            completed = False
            try:
                started = time.monotonic()
                last_meaningful = started
                saw_event = False
                emitted = ""
                thinking_emitted = ""
                chat_id = ""
                await self._start_send(prompt, thinking=thinking, search=search, upstream_model=upstream_model)
                while True:
                    now = time.monotonic()
                    if now - started > self.total_timeout:
                        raise ProviderTimeoutError(self.provider_id, "Qwen total stream timeout")
                    snap = await self._snapshot(prompt)
                    chat_id = snap.get("chat_id") or chat_id
                    if snap.get("error"):
                        signal = detect_provider_risk(snap.get("error"))
                        if signal:
                            raise ProviderError(
                                signal.message,
                                signal.kind,
                                self.provider_id,
                                {"failure_class": signal.failure_class, "wait_hours": signal.wait_hours},
                            )
                        raise ProviderError("Qwen controller send failed", "upstream_error", self.provider_id)
                    visible_signal = detect_provider_risk(snap.get("visible_risk_text"))
                    if visible_signal:
                        raise ProviderError(
                            visible_signal.message,
                            visible_signal.kind,
                            self.provider_id,
                            {"failure_class": visible_signal.failure_class, "wait_hours": visible_signal.wait_hours},
                        )
                    debug = snap.get("debug") or {}
                    if debug.get("assistant_error_present"):
                        upstream_code = str(debug.get("assistant_error_code") or "")
                        upstream_message = str(debug.get("assistant_error_message") or "")[:240]
                        signal = detect_provider_risk(upstream_code + " " + upstream_message)
                        if signal:
                            raise ProviderError(
                                signal.message,
                                signal.kind,
                                self.provider_id,
                                {
                                    "upstream_code": upstream_code,
                                    "message": upstream_message,
                                    "failure_class": signal.failure_class,
                                    "wait_hours": signal.wait_hours,
                                },
                            )
                        error_code = "rate_limit" if upstream_code.lower() == "ratelimited" else "upstream_error"
                        raise ProviderError(
                            "Qwen frontend reported an upstream error",
                            error_code,
                            self.provider_id,
                            {
                                "upstream_code": upstream_code,
                                "message": upstream_message,
                            },
                        )
                    if self.last_backend_request_model and not saw_event:
                        saw_event = True
                        last_meaningful = now
                    if snap.get("has_event"):
                        if not saw_event:
                            saw_event = True
                            last_meaningful = now
                        elif snap.get("answer") != emitted or snap.get("thinking") != thinking_emitted:
                            last_meaningful = now
                    elif not self.last_backend_request_model and now - started > self.first_event_timeout:
                        raise ProviderTimeoutError(self.provider_id, "Qwen first event timeout")

                    full_thinking = snap.get("thinking") or ""
                    if full_thinking.startswith(thinking_emitted) and len(full_thinking) > len(thinking_emitted):
                        delta = full_thinking[len(thinking_emitted):]
                        thinking_emitted = full_thinking
                        yield {
                            "type": "reasoning_delta",
                            "text": delta,
                            "chat_id": chat_id,
                            "model": self.last_backend_request_model or upstream_model or "",
                        }

                    full = snap.get("answer") or ""
                    if full.startswith(emitted) and len(full) > len(emitted):
                        delta = full[len(emitted):]
                        emitted = full
                        last_meaningful = now
                        yield {
                            "type": "text_delta",
                            "text": delta,
                            "chat_id": chat_id,
                            "model": self.last_backend_request_model or upstream_model or "",
                        }
                    elif full and full != emitted:
                        raise ProviderError("Qwen reconstructed stream became non-monotonic", "protocol_error", self.provider_id)

                    if saw_event and now - last_meaningful > self.idle_timeout and not snap.get("terminal"):
                        logger.warning(
                            "Qwen meaningful idle timeout state=%s chat_id=%s answer_len=%s thinking_len=%s answer_status=%s thinking_status=%s net=%s",
                            snap.get("state"),
                            snap.get("chat_id"),
                            len(snap.get("answer") or ""),
                            len(snap.get("thinking") or ""),
                            snap.get("answer_status"),
                            snap.get("thinking_status"),
                            self._network_events[-8:],
                        )
                        raise ProviderTimeoutError(self.provider_id, "Qwen meaningful idle timeout")
                    if (
                        snap.get("terminal")
                        and not self.last_backend_request_model
                        and upstream_model
                        and upstream_model in (self.last_selected_models or [])
                    ):
                        self.last_backend_request_model = upstream_model
                        self._record_network_event(
                            {
                                "kind": "model_inferred_from_terminal_selection",
                                "model": upstream_model,
                            }
                        )
                    if snap.get("terminal") and self.last_backend_request_model:
                        if not emitted and not thinking_emitted:
                            raise ProviderError(
                                "Qwen backend request completed without extractable assistant content",
                                "protocol_error",
                                self.provider_id,
                                {"snapshot": snap.get("debug") or {}},
                            )
                        yield {
                            "type": "done",
                            "text": "",
                            "chat_id": chat_id,
                            "model": self.last_backend_request_model or upstream_model or "",
                        }
                        completed = True
                        return
                    await asyncio.sleep(self.poll_interval)

            except BaseException:
                logger.warning("Resetting Qwen browser transport after failed/cancelled stream", exc_info=True)
                try:
                    await self._reset()
                except Exception:
                    logger.warning("Qwen browser transport reset failed", exc_info=True)
                raise

    async def cancel_active_generation(self, reason: str = "client_cancelled") -> dict:
        """Best-effort stop of an active Qwen Web Chat response."""
        result = {"supported": True, "cancelled": False, "reason": reason, "method": "qwen_frontend_stop"}
        page = self._page
        if not page or page.is_closed():
            result["detail"] = "no_active_page"
            return result
        try:
            stop_result = await page.evaluate(
                """async () => {
                  const x = window.__mwbQwenController;
                  const pool = x?.getPool?.();
                  const s = pool?.currentSession;
                  let called = 0;
                  try { if (x?.stopResponse) { await x.stopResponse(); called++; } } catch (_) {}
                  try { if (pool?.stopAllResponses) { await pool.stopAllResponses(); called++; } } catch (_) {}
                  try { if (s?.stopResponse) { await s.stopResponse(); called++; } } catch (_) {}
                  try { if (s?.waitForStoppedResponseTerminal) { await s.waitForStoppedResponseTerminal(); } } catch (_) {}
                  return {called, state: s?.sessionState || '', url: location.href};
                }"""
            )
            await page.wait_for_timeout(150)
            result.update(stop_result or {})
            result["cancelled"] = bool((stop_result or {}).get("called"))
        except Exception as exc:
            result["error"] = str(exc)[:240]
        return result

    async def close(self) -> None:
        await self._reset()

    async def _reset(self) -> None:
        page, context, pw = self._page, self._context, self._pw
        owns_context = self._owns_context
        # A failed/cancelled CDP stream can leave Qwen's frontend session in
        # `sending`. Disconnecting Playwright alone does not cancel that upstream
        # request, so the next request inherits a poisoned session. Best-effort
        # stop the active response(s) before dropping the local controller handle.
        if page and not page.is_closed():
            try:
                await self.cancel_active_generation("transport_reset")
                try:
                    await page.evaluate("""async () => {
                      const x = window.__mwbQwenController;
                      const pool = x?.getPool?.();
                      const s = pool?.currentSession;
                      try { s?.forceClear?.(); } catch (_) {}
                      return {state:s?.sessionState || ''};
                    }""")
                except Exception:
                    pass
            except Exception:
                logger.debug("Qwen frontend recovery before reset failed", exc_info=True)
        self._page = None
        self._context = None
        self._browser = None
        self._pw = None
        self._owns_context = False
        if owns_context:
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
