import asyncio
import json
import logging
import os
import queue
import threading
import time
import uuid
from typing import AsyncIterator, Optional

import requests

from core.providers import (
    Provider,
    ProviderAuthError,
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
from core.stream_state import StreamTracker
from adapters.qwen_browser_transport import QwenBrowserControllerTransport

logger = logging.getLogger(__name__)


class QwenWebProvider(Provider):
    """Backend-first Qwen Web provider.

    Preferred runtime is Qwen's own frontend controller inside a dedicated
    Playwright profile. This is not DOM chat automation: the controller owns the
    backend request, session and anti-bot integration. A direct-HTTP path is kept
    as an experimental transport and remains fail-closed when its runtime token
    or anti-bot prerequisites are unavailable.
    """

    def __init__(self, config: ProviderConfig):
        super().__init__(config)
        c = config.config
        self._base_url = c.get("base_url", "https://chat.qwen.ai").rstrip("/")
        self._transport_mode = c.get("transport_mode", "browser_controller")
        self._frontend_version = c.get("frontend_version", "0.2.91")
        self._default_upstream_model = c.get("upstream_model", "qwen3.7-plus")
        self._token_env = c.get("token_env", "QWEN_WEB_TOKEN")
        self._token_file = c.get("token_file")
        self._connect_timeout = float(c.get("connect_timeout", 10))
        self._header_timeout = float(c.get("header_timeout", 30))
        self._first_event_timeout = float(c.get("first_event_timeout", 30))
        self._idle_timeout = float(c.get("idle_timeout", 45))
        self._total_timeout = float(c.get("total_timeout", 180))
        self._cleanup = bool(c.get("cleanup", True))
        self._user_agent = c.get(
            "user_agent",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36",
        )
        self._last_upstream_models: list[str] = []
        self._browser = QwenBrowserControllerTransport(
            self.provider_id,
            c.get("profile_dir", r".runtime\qwen-profile"),
            base_url=self._base_url + "/",
            channel=c.get("browser_channel", "chrome"),
            headless=bool(c.get("headless", True)),
            launch_timeout=float(c.get("launch_timeout", 45)),
            first_event_timeout=self._first_event_timeout,
            idle_timeout=self._idle_timeout,
            total_timeout=self._total_timeout,
            poll_interval=float(c.get("poll_interval", 0.08)),
        )

    @property
    def capabilities(self) -> ProviderCapabilities:
        browser_mode = self._transport_mode == "browser_controller"
        return ProviderCapabilities(
            chat_completion=True,
            streaming=True,
            streaming_mode="reconstructed" if browser_mode else "native",
            tools=False,
            vision=False,
            embeddings=False,
            max_context_tokens=1_000_000,
            supported_models=["qwen-web"],
            # Search is visible in the current frontend payload but remains
            # disabled in advertised capabilities until an independent E2 test.
            search=False,
            reasoning=True,
            files=False,
            transport_mode="browser_backend_controller" if browser_mode else "direct_http",
        )

    def _token(self) -> Optional[str]:
        token = os.getenv(self._token_env, "").strip()
        if token:
            return token
        if self._token_file:
            try:
                value = open(self._token_file, "r", encoding="utf-8").read().strip()
                if value:
                    return value
            except OSError:
                pass
        return None

    def _headers(self, *, stream: bool = False) -> dict:
        token = self._token()
        if not token:
            raise ProviderAuthError(self.provider_id, "Qwen Web runtime token is not configured")
        headers = {
            "Accept": "text/event-stream" if stream else "application/json, text/plain, */*",
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
            "Origin": self._base_url,
            "Referer": self._base_url + "/",
            "User-Agent": self._user_agent,
            "source": "web",
            "version": self._frontend_version,
            "x-request-id": str(uuid.uuid4()),
        }
        if stream:
            headers["x-accel-buffering"] = "no"
        return headers

    @staticmethod
    def _is_waf_response(resp: requests.Response) -> bool:
        ctype = (resp.headers.get("content-type") or "").lower()
        if "text/html" not in ctype:
            return False
        body = (resp.text or "")[:4096].lower()
        return "access verification" in body or "aliyuncaptcha" in body or "aliyun_waf" in body

    def _request_json(self, method: str, path: str, *, body: Optional[dict] = None) -> dict:
        try:
            resp = requests.request(
                method,
                self._base_url + path,
                headers=self._headers(),
                json=body,
                timeout=(self._connect_timeout, self._header_timeout),
            )
        except requests.Timeout as e:
            raise ProviderTimeoutError(self.provider_id, "Qwen Web request timed out") from e
        except requests.RequestException as e:
            raise ProviderError("Qwen Web transport failure", "transport_error", self.provider_id) from e

        if self._is_waf_response(resp):
            raise ProviderError(
                "Qwen Web anti-bot challenge requires browser/fingerprint bootstrap",
                "challenge_required",
                self.provider_id,
                {"http_status": resp.status_code},
            )
        if resp.status_code in (401, 403):
            raise ProviderAuthError(self.provider_id, f"Qwen Web authentication failed ({resp.status_code})")
        if resp.status_code == 429:
            raise ProviderError("Qwen Web rate limit", "rate_limit", self.provider_id, {"http_status": 429})
        if not resp.ok:
            raise ProviderError(
                f"Qwen Web upstream HTTP {resp.status_code}",
                "upstream_http_error",
                self.provider_id,
                {"http_status": resp.status_code},
            )
        try:
            data = resp.json()
        except ValueError as e:
            raise ProviderError("Qwen Web returned non-JSON response", "protocol_error", self.provider_id) from e
        if isinstance(data, dict) and data.get("success") is False:
            raise ProviderError("Qwen Web application-level error", "upstream_error", self.provider_id)
        return data

    async def health_check(self) -> bool:
        if self._transport_mode == "browser_controller":
            return await self._browser.health()
        if not self._token():
            return False
        try:
            await asyncio.to_thread(self._request_json, "GET", "/api/v2/models/")
            return True
        except ProviderError:
            return False

    async def list_models(self) -> list[ModelInfo]:
        if self._transport_mode == "browser_controller":
            try:
                self._last_upstream_models = await self._browser.model_ids()
            except ProviderError:
                # Canonical mapping remains discoverable even when upstream
                # model enumeration is temporarily unavailable.
                self._last_upstream_models = []
            return [ModelInfo(id="qwen-web", owned_by="qwen-web", provider=self.provider_id)]
        if self._token():
            data = await asyncio.to_thread(self._request_json, "GET", "/api/v2/models/")
            upstream = data.get("data", {}).get("data", []) if isinstance(data, dict) else []
            self._last_upstream_models = [m.get("id") for m in upstream if isinstance(m, dict) and m.get("id")]
        return [ModelInfo(id="qwen-web", owned_by="qwen-web", provider=self.provider_id)]

    def _create_chat(self, upstream_model: str) -> str:
        body = {
            "chatId": "",
            "models": [upstream_model],
            "project_id": "",
            "timestamp": int(time.time() * 1000),
            "chat_type": "t2t",
            "chat_mode": "normal",
        }
        data = self._request_json("POST", "/api/v2/chats/new", body=body)
        chat_id = data.get("data", {}).get("id") if isinstance(data, dict) else None
        if not chat_id:
            raise ProviderError("Qwen Web create-chat response missing id", "protocol_error", self.provider_id)
        return str(chat_id)

    def _delete_chat(self, chat_id: str) -> None:
        try:
            self._request_json("DELETE", f"/api/v2/chats/{chat_id}")
        except Exception:
            logger.warning("Qwen cleanup failed provider=%s", self.provider_id)

    @staticmethod
    def _request_text(request: ChatCompletionRequest) -> str:
        parts = []
        for message in request.messages:
            role = message.get("role", "user")
            content = message.get("content") or ""
            if role == "system":
                parts.append(f"System: {content}")
            elif role == "user":
                parts.append(content)
            elif role == "assistant":
                parts.append(f"Assistant: {content}")
            elif role == "tool":
                parts.append(f"Tool result: {content}")
        return "\n\n".join(p for p in parts if p).strip()

    def _payload(self, chat_id: str, upstream_model: str, request: ChatCompletionRequest) -> dict:
        opts = request.provider_options or {}
        thinking = opts.get("thinking")
        if thinking is None:
            thinking = True
        search = bool(opts.get("search", False))
        thinking_mode = "Auto" if thinking else "Disabled"
        now = int(time.time())
        msg = {
            "id": None,
            "fid": str(uuid.uuid4()),
            "parentId": None,
            "childrenIds": [str(uuid.uuid4())],
            "role": "user",
            "content": self._request_text(request),
            "user_action": "chat",
            "files": [],
            "timestamp": now,
            "models": [upstream_model],
            "model": "",
            "chat_type": "t2t",
            "feature_config": {
                "thinking_enabled": bool(thinking),
                "output_schema": "phase",
                "research_mode": "normal",
                "auto_thinking": bool(thinking),
                "thinking_mode": thinking_mode,
                "thinking_format": "summary",
                "auto_search": search,
            },
            "extra": {"meta": {"subChatType": "t2t"}},
            "sub_chat_type": "t2t",
            "parent_id": None,
        }
        return {
            "stream": True,
            "version": "2.1",
            "incremental_output": True,
            "chatId": chat_id,
            "parentId": "",
            "chat_id": chat_id,
            "chat_mode": "normal",
            "model": upstream_model,
            "parent_id": None,
            "messages": [msg],
            "timestamp": now,
        }

    @staticmethod
    def _classify_sse_object(obj: dict) -> tuple[str, Optional[str], bool, Optional[dict]]:
        if obj.get("error") or obj.get("success") is False:
            return "error", None, False, obj.get("error") if isinstance(obj.get("error"), dict) else obj
        choices = obj.get("choices") or []
        if not choices:
            if obj.get("response.created"):
                return "meta", None, False, None
            return "meta", None, False, None
        delta = choices[0].get("delta") or {}
        phase = delta.get("phase")
        status = delta.get("status")
        content = delta.get("content") or ""
        terminal = status == "finished" and phase == "answer"
        if phase == "answer" and content:
            return "answer", content, terminal, None
        if terminal:
            return "terminal", None, True, None
        return "meta", None, False, None

    def _stream_worker(self, chat_id: str, upstream_model: str, request: ChatCompletionRequest, out: queue.Queue) -> None:
        tracker = StreamTracker(request_id=str(uuid.uuid4()))
        resp = None
        try:
            payload = self._payload(chat_id, upstream_model, request)
            resp = requests.post(
                self._base_url + f"/api/v2/chat/completions?chat_id={chat_id}",
                headers=self._headers(stream=True),
                json=payload,
                stream=True,
                timeout=(self._connect_timeout, max(self._idle_timeout, self._first_event_timeout)),
            )
            tracker.headers_received()
            if self._is_waf_response(resp):
                raise ProviderError(
                    "Qwen Web anti-bot challenge requires browser/fingerprint bootstrap",
                    "challenge_required",
                    self.provider_id,
                    {"http_status": resp.status_code},
                )
            if resp.status_code in (401, 403):
                raise ProviderAuthError(self.provider_id, f"Qwen Web authentication failed ({resp.status_code})")
            if resp.status_code == 429:
                raise ProviderError("Qwen Web rate limit", "rate_limit", self.provider_id, {"http_status": 429})
            if not resp.ok:
                raise ProviderError(
                    f"Qwen Web upstream HTTP {resp.status_code}",
                    "upstream_http_error",
                    self.provider_id,
                    {"http_status": resp.status_code},
                )
            ctype = (resp.headers.get("content-type") or "").lower()
            if "text/event-stream" not in ctype:
                raise ProviderError("Qwen completion was not SSE", "protocol_error", self.provider_id)

            for raw in resp.iter_lines(decode_unicode=True):
                if raw is None:
                    continue
                line = raw.strip()
                if not line or line.startswith(":") or not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if not data or data == "[DONE]":
                    continue
                try:
                    obj = json.loads(data)
                except ValueError:
                    out.put(("error", ProviderError("Malformed Qwen SSE JSON", "protocol_error", self.provider_id)))
                    return
                tracker.meaningful_event(len(raw.encode("utf-8", errors="ignore")))
                kind, text, terminal, upstream_error = self._classify_sse_object(obj)
                if kind == "error":
                    out.put(("error", ProviderError("Qwen error inside HTTP 200 stream", "upstream_stream_error", self.provider_id)))
                    return
                if text:
                    out.put(("data", text))
                if terminal:
                    tracker.complete("answer_finished")
                    out.put(("done", None))
                    return
            tracker.complete("eof")
            out.put(("done", None))
        except Exception as e:
            tracker.fail(type(e).__name__)
            out.put(("error", e))
        finally:
            if resp is not None:
                resp.close()

    async def _iterate_text(self, chat_id: str, upstream_model: str, request: ChatCompletionRequest):
        q: queue.Queue = queue.Queue(maxsize=128)
        thread = threading.Thread(
            target=self._stream_worker,
            args=(chat_id, upstream_model, request, q),
            daemon=True,
        )
        thread.start()
        started = time.monotonic()
        first = True
        while True:
            elapsed = time.monotonic() - started
            if elapsed >= self._total_timeout:
                raise ProviderTimeoutError(self.provider_id, "Qwen total stream timeout")
            wait_for = self._first_event_timeout if first else self._idle_timeout
            wait_for = min(wait_for, self._total_timeout - elapsed)
            try:
                kind, value = await asyncio.wait_for(asyncio.to_thread(q.get), timeout=wait_for)
            except asyncio.TimeoutError as e:
                label = "first event" if first else "meaningful idle"
                raise ProviderTimeoutError(self.provider_id, f"Qwen {label} timeout") from e
            first = False
            if kind == "data":
                yield value
            elif kind == "done":
                return
            elif kind == "error":
                if isinstance(value, ProviderError):
                    raise value
                if isinstance(value, requests.Timeout):
                    raise ProviderTimeoutError(self.provider_id, "Qwen stream transport timeout") from value
                raise ProviderError("Qwen stream failure", "transport_error", self.provider_id) from value

    async def chat_completion(
        self,
        request: ChatCompletionRequest,
        session: Optional[SessionContext] = None,
    ) -> ChatCompletionResponse:
        if request.model != "qwen-web":
            raise ProviderError("Unsupported Qwen model", "invalid_model", self.provider_id)
        if request.tools:
            raise ProviderError("Qwen tools are not enabled until E2 validation passes", "unsupported_tools", self.provider_id)
        if self._transport_mode == "browser_controller":
            opts = request.provider_options or {}
            pieces: list[str] = []
            chat_id = ""
            async for event in self._browser.stream_text(
                self._request_text(request),
                thinking=opts.get("thinking", True),
                search=bool(opts.get("search", False)),
            ):
                chat_id = event.get("chat_id") or chat_id
                if event.get("type") == "text_delta":
                    pieces.append(event.get("text") or "")
            return ChatCompletionResponse(
                id=self._generate_id(),
                created=self._current_timestamp(),
                model="qwen-web",
                choices=[Choice(index=0, message=Message(role="assistant", content="".join(pieces)), finish_reason="stop")],
                usage=Usage(),
                provider_meta={
                    "provider": self.provider_id,
                    "transport_mode": "browser_backend_controller",
                    "streaming_mode": "reconstructed",
                    "frontend_version": self._browser.frontend_version,
                    "session_mode": self._browser.last_session_mode,
                    "conversation_id": chat_id or None,
                },
            )
        upstream_model = (request.provider_options or {}).get("upstream_model") or self._default_upstream_model
        chat_id = await asyncio.to_thread(self._create_chat, upstream_model)
        pieces = []
        try:
            async for text in self._iterate_text(chat_id, upstream_model, request):
                pieces.append(text)
        finally:
            if self._cleanup and not request.conversation_id:
                await asyncio.to_thread(self._delete_chat, chat_id)
        content = "".join(pieces)
        return ChatCompletionResponse(
            id=self._generate_id(),
            created=self._current_timestamp(),
            model="qwen-web",
            choices=[Choice(index=0, message=Message(role="assistant", content=content), finish_reason="stop")],
            usage=Usage(),
            provider_meta={
                "provider": self.provider_id,
                "transport_mode": "direct_http",
                "streaming_mode": "native",
                "upstream_model": upstream_model,
                "frontend_version": self._frontend_version,
            },
        )

    async def chat_completion_stream(
        self,
        request: ChatCompletionRequest,
        session: Optional[SessionContext] = None,
    ) -> AsyncIterator[ChatCompletionChunk]:
        if request.model != "qwen-web":
            raise ProviderError("Unsupported Qwen model", "invalid_model", self.provider_id)
        if request.tools:
            raise ProviderError("Qwen tools are not enabled until E2 validation passes", "unsupported_tools", self.provider_id)
        if self._transport_mode == "browser_controller":
            opts = request.provider_options or {}
            chunk_id = self._generate_id()
            chat_id = ""
            async for event in self._browser.stream_text(
                self._request_text(request),
                thinking=opts.get("thinking", True),
                search=bool(opts.get("search", False)),
            ):
                chat_id = event.get("chat_id") or chat_id
                if event.get("type") != "text_delta":
                    continue
                yield ChatCompletionChunk(
                    id=chunk_id,
                    created=self._current_timestamp(),
                    model="qwen-web",
                    choices=[ChunkChoice(index=0, delta=Delta(content=event.get("text") or ""), finish_reason=None)],
                    provider_meta={
                        "provider": self.provider_id,
                        "transport_mode": "browser_backend_controller",
                        "streaming_mode": "reconstructed",
                        "frontend_version": self._browser.frontend_version,
                        "session_mode": self._browser.last_session_mode,
                        "conversation_id": chat_id or None,
                    },
                )
            yield ChatCompletionChunk(
                id=chunk_id,
                created=self._current_timestamp(),
                model="qwen-web",
                choices=[ChunkChoice(index=0, delta=Delta(), finish_reason="stop")],
                provider_meta={
                    "provider": self.provider_id,
                    "transport_mode": "browser_backend_controller",
                    "streaming_mode": "reconstructed",
                    "frontend_version": self._browser.frontend_version,
                    "session_mode": self._browser.last_session_mode,
                    "conversation_id": chat_id or None,
                },
            )
            return
        upstream_model = (request.provider_options or {}).get("upstream_model") or self._default_upstream_model
        chat_id = await asyncio.to_thread(self._create_chat, upstream_model)
        chunk_id = self._generate_id()
        try:
            async for text in self._iterate_text(chat_id, upstream_model, request):
                yield ChatCompletionChunk(
                    id=chunk_id,
                    created=self._current_timestamp(),
                    model="qwen-web",
                    choices=[ChunkChoice(index=0, delta=Delta(content=text), finish_reason=None)],
                    provider_meta={
                        "provider": self.provider_id,
                        "transport_mode": "direct_http",
                        "streaming_mode": "native",
                        "upstream_model": upstream_model,
                    },
                )
            yield ChatCompletionChunk(
                id=chunk_id,
                created=self._current_timestamp(),
                model="qwen-web",
                choices=[ChunkChoice(index=0, delta=Delta(), finish_reason="stop")],
                provider_meta={
                    "provider": self.provider_id,
                    "transport_mode": "direct_http",
                    "streaming_mode": "native",
                    "upstream_model": upstream_model,
                },
            )
        finally:
            if self._cleanup and not request.conversation_id:
                await asyncio.to_thread(self._delete_chat, chat_id)

    async def close(self) -> None:
        await self._browser.close()


def create_qwen_web_provider(
    provider_id: str = "qwen-web",
    priority: int = 90,
    **config_values,
) -> QwenWebProvider:
    browser_mode = config_values.get("transport_mode", "browser_controller") == "browser_controller"
    config = ProviderConfig(
        provider_id=provider_id,
        provider_type=ProviderType.QWEN_WEB,
        enabled=True,
        priority=priority,
        config=config_values,
        capabilities=ProviderCapabilities(
            chat_completion=True,
            streaming=True,
            streaming_mode="reconstructed" if browser_mode else "native",
            tools=False,
            vision=False,
            embeddings=False,
            max_context_tokens=1_000_000,
            supported_models=["qwen-web"],
            search=False,
            reasoning=True,
            files=False,
            transport_mode="browser_backend_controller" if browser_mode else "direct_http",
        ),
    )
    return QwenWebProvider(config)
