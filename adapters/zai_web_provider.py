import asyncio
import json
import logging
import time
from typing import AsyncIterator, Optional

import requests
from playwright.async_api import async_playwright

from core.providers import (
    Provider,
    ProviderCapabilities,
    ProviderConfig,
    ProviderError,
    ProviderTimeoutError,
    ProviderType,
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChatCompletionChunk,
    Choice,
    Message,
    Usage,
    ChunkChoice,
    Delta,
    ModelInfo,
    SessionContext,
)

logger = logging.getLogger(__name__)


class ZaiWebProvider(Provider):
    """Backend-first Z.ai Web provider.

    Model discovery uses the public same-origin backend. Completion uses the
    official frontend to generate provider-owned X-Signature and CAPTCHA proof,
    then captures/parses the resulting backend SSE response from the browser
    fetch stream. This is not CAPTCHA bypass and does not copy browser tokens.
    """

    def __init__(self, config: ProviderConfig):
        super().__init__(config)
        c = config.config
        self._base_url = c.get("base_url", "https://chat.z.ai").rstrip("/")
        self._frontend_version = c.get("frontend_version", "prod-fe-1.1.93")
        self._transport_mode = c.get("transport_mode", "browser_ui_capture")
        self._cdp_url = c.get("cdp_url", "http://127.0.0.1:9223")
        self._connect_timeout = float(c.get("connect_timeout", 10))
        self._header_timeout = float(c.get("header_timeout", 30))
        self._total_timeout = float(c.get("total_timeout", 180))
        self._poll_interval = float(c.get("poll_interval", 0.25))
        self._user_agent = c.get(
            "user_agent",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36",
        )
        self._pw = None
        self._browser = None
        self._context = None
        self._page = None
        self._request_lock = None
        self._last_models: list[ModelInfo] = []

    @property
    def capabilities(self) -> ProviderCapabilities:
        operational = self._transport_mode == "browser_ui_capture"
        return ProviderCapabilities(
            chat_completion=operational,
            streaming=operational,
            streaming_mode="buffered_sse_capture" if operational else "blocked_by_challenge",
            tools=False,
            vision=False,
            embeddings=False,
            max_context_tokens=128_000,
            supported_models=["zai-web"],
            search=False,
            reasoning=True if operational else False,
            files=False,
            transport_mode="browser_frontend_backend_sse_capture" if operational else "backend_discovery_only",
        )

    def _headers(self) -> dict:
        return {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Accept-Language": "en-US",
            "X-FE-Version": self._frontend_version,
            "Origin": self._base_url,
            "Referer": self._base_url + "/",
            "User-Agent": self._user_agent,
        }

    def _get_json(self, path: str) -> dict:
        try:
            resp = requests.get(
                self._base_url + path,
                headers=self._headers(),
                timeout=(self._connect_timeout, self._header_timeout),
            )
        except requests.Timeout as e:
            raise ProviderTimeoutError(self.provider_id, "Z.ai Web request timed out") from e
        except requests.RequestException as e:
            raise ProviderError("Z.ai Web transport failure", "transport_error", self.provider_id) from e
        if resp.status_code in (401, 403):
            raise ProviderError("Z.ai Web authentication or browser session required", "auth_or_session_required", self.provider_id, {"http_status": resp.status_code})
        if resp.status_code == 429:
            raise ProviderError("Z.ai Web rate limit", "rate_limit", self.provider_id, {"http_status": 429})
        if not resp.ok:
            raise ProviderError("Z.ai Web upstream HTTP error", "upstream_http_error", self.provider_id, {"http_status": resp.status_code})
        try:
            return resp.json()
        except ValueError as e:
            raise ProviderError("Z.ai Web returned non-JSON response", "protocol_error", self.provider_id) from e

    async def _connect(self):
        try:
            self._pw = await async_playwright().start()
            self._browser = await self._pw.chromium.connect_over_cdp(self._cdp_url)
            self._context = self._browser.contexts[0] if self._browser.contexts else None
            if not self._context:
                raise ProviderError("Browser context not found", "browser_unavailable", self.provider_id)
        except Exception as e:
            await self._cleanup_connection()
            if isinstance(e, ProviderError):
                raise
            raise ProviderError("Failed to connect to Chrome CDP for Z.ai", "browser_unavailable", self.provider_id, {"cdp_url": self._cdp_url}) from e

    async def _cleanup_connection(self):
        try:
            if self._pw:
                await self._pw.stop()
        except Exception:
            pass
        self._pw = None
        self._browser = None
        self._context = None
        self._page = None

    async def _ensure_page(self):
        await self._cleanup_connection()
        await self._connect()
        assert self._context is not None
        for p in self._context.pages:
            if "chat.z.ai" in p.url and not p.is_closed():
                self._page = p
                break
        if self._page is None:
            self._page = await self._context.new_page()
            await self._page.goto(self._base_url + "/", wait_until="domcontentloaded", timeout=30000)
        await self._page.wait_for_selector("textarea", timeout=30000)
        await self._install_fetch_capture()

    async def _install_fetch_capture(self):
        assert self._page is not None
        await self._page.evaluate(
            """
            () => {
              window.__mwbZaiCapture = [];
              if (window.__mwbZaiFetchWrapped) return true;
              const orig = window.fetch.bind(window);
              window.__mwbZaiFetchWrapped = true;
              window.fetch = async (...args) => {
                const req = args[0];
                const init = args[1] || {};
                const url = typeof req === 'string' ? req : ((req && req.url) || '');
                const method = (init.method || (req && req.method) || 'GET').toUpperCase();
                const isZaiCompletion = String(url).includes('/api/') && String(url).includes('/chat/completions');
                const resp = await orig(...args);
                if (isZaiCompletion) {
                  const item = {kind:'response', t:Date.now(), method, url:String(url), status:resp.status, contentType:resp.headers.get('content-type'), text:''};
                  try {
                    resp.clone().text().then(txt => { item.text = txt; }).catch(e => { item.error = String(e); });
                  } catch(e) { item.error = String(e); }
                  window.__mwbZaiCapture.push(item);
                }
                return resp;
              };
              return true;
            }
            """
        )

    @staticmethod
    def _request_text(request: ChatCompletionRequest) -> str:
        parts = []
        for message in request.messages:
            role = message.get("role", "user")
            content = message.get("content") or ""
            if role == "system":
                parts.append(f"System: {content}")
            elif role == "user":
                parts.append(str(content))
            elif role == "assistant":
                parts.append(f"Assistant: {content}")
            elif role == "tool":
                parts.append(f"Tool result: {content}")
        return "\n\n".join(p for p in parts if p).strip()

    async def _submit_via_frontend(self, prompt: str) -> str:
        assert self._page is not None
        await self._page.evaluate("window.__mwbZaiCapture = []")
        await self._page.locator("textarea").last.fill(prompt)
        # Z.ai's send button is not consistently type=submit. Enter uses the
        # frontend's own submit handler without our code constructing signed
        # backend requests.
        await self._page.locator("textarea").last.press("Enter")

        deadline = time.monotonic() + self._total_timeout
        last_text = ""
        while time.monotonic() < deadline:
            state = await self._page.evaluate(
                """
                () => {
                  const body = document.body.innerText || '';
                  const captures = window.__mwbZaiCapture || [];
                  return {
                    hasCaptcha: /captcha|verification|robot|slider|verify|Slide/i.test(body),
                    stopVisible: /\bStop\b/.test(body),
                    captures: captures.map(x => ({status:x.status, contentType:x.contentType, text:x.text || '', error:x.error || null})).slice(-4),
                  };
                }
                """
            )
            if state.get("hasCaptcha"):
                raise ProviderError("Z.ai CAPTCHA requires manual user completion in the browser", "captcha_required", self.provider_id)
            captures = state.get("captures") or []
            for item in reversed(captures):
                text = item.get("text") or ""
                if text:
                    last_text = text
                    parsed = self._parse_sse_text(text)
                    if parsed.get("done"):
                        return parsed.get("answer", "").strip()
            await asyncio.sleep(self._poll_interval)
        raise ProviderTimeoutError(self.provider_id, "Z.ai completion timed out")

    @staticmethod
    def _parse_sse_text(text: str) -> dict:
        answer = []
        thinking = []
        done = False
        for line in text.splitlines():
            if not line.startswith("data: "):
                continue
            raw = line[6:].strip()
            if not raw or raw == "[DONE]":
                done = True
                continue
            try:
                obj = json.loads(raw)
            except Exception:
                continue
            data = obj.get("data") if isinstance(obj, dict) else None
            if not isinstance(data, dict):
                continue
            phase = data.get("phase")
            delta = data.get("delta_content") or ""
            if phase == "answer" and delta:
                answer.append(delta)
            elif phase == "thinking" and delta:
                thinking.append(delta)
            if data.get("done") or phase == "done":
                done = True
        return {"answer": "".join(answer), "thinking": "".join(thinking), "done": done}

    async def health_check(self) -> bool:
        if self._transport_mode == "browser_ui_capture":
            try:
                await self._ensure_page()
                return True
            except ProviderError:
                return False
        try:
            await self.list_models()
            return True
        except ProviderError:
            return False

    async def list_models(self) -> list[ModelInfo]:
        try:
            data = await asyncio.to_thread(self._get_json, "/api/models")
        except ProviderError:
            if self._transport_mode != "browser_ui_capture":
                raise
            await self._ensure_page()
            assert self._page is not None
            data = await self._page.evaluate(
                """
                async () => {
                  const r = await fetch('/api/models', {credentials:'include'});
                  if (!r.ok) throw new Error('model discovery failed: ' + r.status);
                  return await r.json();
                }
                """
            )
        raw_models = data.get("data", []) if isinstance(data, dict) else []
        models: list[ModelInfo] = [ModelInfo(id="zai-web", owned_by="zai-web", provider=self.provider_id)]
        for m in raw_models:
            if not isinstance(m, dict) or not m.get("id"):
                continue
            models.append(ModelInfo(id=f"zai:{m['id']}", owned_by="zai-web", provider=self.provider_id))
        self._last_models = models
        return models

    async def chat_completion(
        self,
        request: ChatCompletionRequest,
        session: Optional[SessionContext] = None,
    ) -> ChatCompletionResponse:
        if request.model != "zai-web":
            raise ProviderError("Z.ai provider only accepts canonical model zai-web", "unsupported_model", self.provider_id)
        if request.tools:
            raise ProviderError("Z.ai tool calling is not enabled until E2 tool round-trip acceptance", "unsupported_tools", self.provider_id)
        if self._transport_mode != "browser_ui_capture":
            raise ProviderError(
                "Z.ai completion transport is not enabled",
                "challenge_required",
                self.provider_id,
                {"completion_path": "/api/v2/chat/completions", "transport_mode": self._transport_mode},
            )
        if self._request_lock is None:
            self._request_lock = asyncio.Lock()
        async with self._request_lock:
            await self._ensure_page()
            content = await self._submit_via_frontend(self._request_text(request))
        return ChatCompletionResponse(
            id=self._generate_id(),
            created=self._current_timestamp(),
            model=request.model,
            choices=[Choice(index=0, message=Message(role="assistant", content=content), finish_reason="stop")],
            usage=Usage(),
            provider_meta={
                "provider": self.provider_id,
                "transport_mode": "browser_frontend_backend_sse_capture",
                "streaming_mode": "buffered_sse_capture",
                "frontend_version": self._frontend_version,
            },
        )

    async def chat_completion_stream(
        self,
        request: ChatCompletionRequest,
        session: Optional[SessionContext] = None,
    ) -> AsyncIterator[ChatCompletionChunk]:
        response = await self.chat_completion(request, session)
        if response.choices[0].message.content:
            yield ChatCompletionChunk(
                id=response.id,
                created=response.created,
                model=response.model,
                choices=[ChunkChoice(index=0, delta=Delta(role="assistant", content=response.choices[0].message.content), finish_reason=None)],
                provider_meta=response.provider_meta,
            )
        yield ChatCompletionChunk(
            id=response.id,
            created=response.created,
            model=response.model,
            choices=[ChunkChoice(index=0, delta=Delta(), finish_reason="stop")],
            provider_meta=response.provider_meta,
        )

    async def close(self) -> None:
        await self._cleanup_connection()


def create_zai_web_provider(provider_id: str = "zai-web", priority: int = 80, **kwargs) -> ZaiWebProvider:
    config = ProviderConfig(
        provider_id=provider_id,
        provider_type=ProviderType.ZAI_WEB,
        priority=priority,
        config=kwargs,
    )
    return ZaiWebProvider(config)
