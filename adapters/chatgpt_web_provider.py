import asyncio
import logging
from typing import AsyncIterator, Optional
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout
from core.providers import (
    Provider,
    ProviderConfig,
    ProviderType,
    ProviderCapabilities,
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
    ProviderError,
    ProviderUnavailableError,
    ProviderTimeoutError,
)
from core.mcp import mcp_session_manager
from core.files import (
    ensure_file_exists,
    build_chunked_messages,
    extract_download_links,
)
from core.parser import parse_sse_chunks, extract_text_from_sse_events

logger = logging.getLogger(__name__)

INPUT_SELECTOR = "#prompt-textarea"
SEND_SELECTOR = "button[data-testid='send-button']"
ASSISTANT_SELECTOR = "[data-message-author-role='assistant']"
FILE_INPUT_SELECTOR = "input[type='file']"
UPLOAD_READY_SELECTOR = "button[data-testid='send-button'], text=Upload complete, .upload-complete"
MAX_FILE_UPLOAD_TIMEOUT = 600000
LONG_TEXT_CHUNK_SIZE = 2048


class ChatGPTWebProvider(Provider):
    def __init__(self, config: ProviderConfig):
        super().__init__(config)
        self._cdp_url = config.config.get("cdp_url", "http://127.0.0.1:9222")
        self._chatgpt_url = config.config.get("chatgpt_url", "https://chatgpt.com")
        self._adapter = config.config.get("adapter", "dom")
        self._headless = config.config.get("headless", False)
        self._timeout = config.config.get("timeout", 120)
        self._long_text_chunk_size = config.config.get("long_text_chunk_size", LONG_TEXT_CHUNK_SIZE)
        self._pw = None
        self._browser = None
        self._context = None
        self._page = None
        # Requests must not manipulate the same ChatGPT page concurrently.
        # The lock is created lazily because asyncio primitives belong to the
        # persistent provider event loop used by the Flask bridge.
        self._request_lock = None
    
    @property
    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            chat_completion=True,
            # DOM mode also supports the compatibility streaming endpoint by
            # returning the completed response as a single chunk.  Advertising
            # this capability lets OpenAI-compatible clients such as Kilo
            # select the provider when they send stream=true.
            streaming=True,
            tools=True,
            vision=False,
            embeddings=False,
            max_context_tokens=128000,
            # ChatGPT Web is model-agnostic from the gateway's perspective;
            # accept arbitrary client model aliases (gpt-4.1, o3, etc.).
            supported_models=[],
        )
    
    async def health_check(self) -> bool:
        """Check provider availability without mutating browser state.

        A health check must not create tabs, navigate pages, or report failure
        only because an authenticated ChatGPT page is not already open. The
        gateway availability depends on the provider runtime (CDP endpoint)
        being reachable; actual completion readiness is tested separately.
        """
        pw = None
        try:
            pw = await async_playwright().start()
            browser = await pw.chromium.connect_over_cdp(self._cdp_url)
            context = browser.contexts[0] if browser.contexts else None
            if not context:
                return False
            return True
        except Exception as e:
            logger.warning(f"Health check failed for {self.provider_id}: {e}")
            return False
        finally:
            if pw:
                await pw.stop()
    
    async def _ensure_page(self):
        # Always create a fresh connection to avoid stale state issues
        await self._cleanup_connection()
        await self._connect()
        
        if self._page is None:
            for p in self._context.pages:
                if "chatgpt.com" in p.url and not p.is_closed():
                    self._page = p
                    break
            
            if not self._page:
                self._page = await self._context.new_page()
                await self._page.goto(self._chatgpt_url, wait_until="domcontentloaded", timeout=30000)
    
    async def _connect(self):
        try:
            self._pw = await async_playwright().start()
            self._browser = await self._pw.chromium.connect_over_cdp(self._cdp_url)
            self._context = self._browser.contexts[0] if self._browser.contexts else None
            if not self._context:
                raise ProviderUnavailableError(self.provider_id, "Browser context not found")
            self._page = None
        except Exception as e:
            await self._cleanup_connection()
            raise ProviderUnavailableError(self.provider_id, f"Failed to connect: {e}")
    
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
    
    async def _send_message(self, message: str):
        if self._page is None:
            raise ProviderError("Page is not initialized", "page_not_initialized", self.provider_id)
        await self._page.wait_for_selector(INPUT_SELECTOR, timeout=30000)
        input_box = self._page.locator(INPUT_SELECTOR)
        await input_box.click()
        await input_box.press("Control+a")
        await input_box.press("Delete")
        await input_box.press_sequentially(message)
        
        send_btn = self._page.locator(SEND_SELECTOR)
        if await send_btn.count() > 0 and await send_btn.is_visible():
            await send_btn.click()
        else:
            await input_box.press("Enter")
    
    async def _wait_for_assistant(self, timeout: int = 120000):
        await self._page.wait_for_selector(ASSISTANT_SELECTOR, timeout=timeout)

    async def _wait_for_new_assistant(self, previous_count: int, previous_text: str = "", timeout: int = 120000):
        """Wait until ChatGPT has produced a response for the current request.

        Merely waiting for the assistant selector is insufficient on the second
        request because the previous assistant message is still present.
        """
        deadline = asyncio.get_running_loop().time() + (timeout / 1000)
        messages = self._page.locator(ASSISTANT_SELECTOR)
        while asyncio.get_running_loop().time() < deadline:
            count = await messages.count()
            if count > previous_count:
                latest = messages.nth(count - 1)
                text = (await latest.inner_text(timeout=10000)).strip()
                if text:
                    return
            elif count == previous_count and count > 0:
                latest = messages.nth(count - 1)
                text = (await latest.inner_text(timeout=10000)).strip()
                if text and text != previous_text:
                    return
            await asyncio.sleep(0.5)
        raise PlaywrightTimeout(f"Timed out waiting for a new assistant response after {timeout}ms")
    
    async def _extract_latest_assistant_text(self) -> str:
        assistant_messages = self._page.locator(ASSISTANT_SELECTOR)
        count = await assistant_messages.count()
        latest = assistant_messages.nth(count - 1)
        
        old_text = ""
        for _ in range(30):
            try:
                new_text = (await latest.inner_text(timeout=10000)).strip()
            except Exception:
                try:
                    new_text = (await latest.evaluate("el => el.innerText || el.textContent || ''")).strip()
                except Exception:
                    new_text = ""
            if new_text and new_text == old_text:
                break
            old_text = new_text
            await asyncio.sleep(1)
        
        try:
            return (await latest.inner_text(timeout=10000)).strip()
        except Exception:
            try:
                return (await latest.evaluate("el => el.innerText || el.textContent || ''")).strip()
            except Exception:
                return old_text.strip()
    
    async def _upload_file(self, file_path: str):
        ensure_file_exists(file_path)
        
        add_btn = self._page.locator("button[data-testid='composer-plus-btn']")
        if await add_btn.count() == 0:
            raise ProviderError("File upload button not found", "upload_failed", self.provider_id)
        
        await add_btn.click()
        
        try:
            file_input = self._page.locator(FILE_INPUT_SELECTOR)
            await file_input.set_input_files(file_path)
        except Exception:
            await add_btn.click()
            file_input = self._page.locator(FILE_INPUT_SELECTOR)
            await file_input.set_input_files(file_path)
        
        try:
            await self._page.wait_for_selector(UPLOAD_READY_SELECTOR, timeout=MAX_FILE_UPLOAD_TIMEOUT)
        except PlaywrightTimeout:
            logger.warning("File upload timeout; continuing anyway")
    
    async def _upload_files(self, file_paths):
        if not file_paths:
            return
        if isinstance(file_paths, str):
            file_paths = [file_paths]
        
        for path in file_paths:
            await self._upload_file(path)
    
    async def chat_completion(
        self,
        request: ChatCompletionRequest,
        session: Optional[SessionContext] = None
    ) -> ChatCompletionResponse:
        if self._request_lock is None:
            self._request_lock = asyncio.Lock()
        async with self._request_lock:
            last_error = None
            for attempt in range(2):
                try:
                    await self._ensure_page()
                    return await self._do_chat_completion(request, session)
                except Exception as e:
                    last_error = e
                    if attempt == 0:
                        logger.warning(f"Chat completion failed, reconnecting: {e}")
                        await self._cleanup_connection()
                        continue
                    break
            raise last_error
    
    async def _do_chat_completion(
        self,
        request: ChatCompletionRequest,
        session: Optional[SessionContext] = None
    ) -> ChatCompletionResponse:
        conversation_id = request.conversation_id or f"conv-{self._generate_id()}"
        mcp_session = mcp_session_manager.get_or_create_session(conversation_id, self)
        
        if session and session.provider_session_id:
            pass
        
        file_paths = request.provider_options.get("file_paths", []) if request.provider_options else []
        
        try:
            assistant_messages = self._page.locator(ASSISTANT_SELECTOR)
            previous_count = await assistant_messages.count()
            previous_text = ""
            if previous_count:
                previous_text = (await assistant_messages.nth(previous_count - 1).inner_text(timeout=10000)).strip()

            if file_paths:
                await self._upload_files(file_paths)
            
            user_content = request.messages[-1].get("content", "") if request.messages else ""
            if isinstance(user_content, list):
                user_content = "".join(
                    str(item.get("text", ""))
                    for item in user_content
                    if isinstance(item, dict) and item.get("type") in ("text", "input_text")
                )
            elif not isinstance(user_content, str):
                user_content = str(user_content)
            chunks = build_chunked_messages(user_content, chunk_size=self._long_text_chunk_size)
            
            for idx, chunk in enumerate(chunks):
                prefix = f"[Part {idx + 1}/{len(chunks)}] " if len(chunks) > 1 else ""
                await self._send_message(f"{prefix}{chunk}")
                if idx < len(chunks) - 1:
                    await asyncio.sleep(2)
            
            await self._wait_for_new_assistant(
                previous_count,
                previous_text,
                timeout=self._timeout * 1000,
            )
            response_text = await self._extract_latest_assistant_text()
            downloads = await extract_download_links(self._page)
            
            mcp_session_manager.update_provider_session_id(conversation_id, self._page.url)
            
            return ChatCompletionResponse(
                id=self._generate_id(),
                created=self._current_timestamp(),
                model=request.model,
                choices=[
                    Choice(
                        index=0,
                        message=Message(role="assistant", content=response_text),
                        finish_reason="stop",
                    )
                ],
                usage=Usage(
                    prompt_tokens=len(user_content) // 4,
                    completion_tokens=len(response_text) // 4,
                    total_tokens=(len(user_content) + len(response_text)) // 4,
                ),
                provider_meta={
                    "chunks_sent": len(chunks),
                    "downloads": downloads,
                    "conversation_id": conversation_id,
                },
            )
        except PlaywrightTimeout as e:
            raise ProviderTimeoutError(self.provider_id, f"Request timeout: {e}")
        except Exception as e:
            import traceback
            logger.error(f"Chat completion error: {e}\n{traceback.format_exc()}")
            raise ProviderError(str(e), "chat_completion_failed", self.provider_id)
    
    async def chat_completion_stream(
        self,
        request: ChatCompletionRequest,
        session: Optional[SessionContext] = None
    ) -> AsyncIterator[ChatCompletionChunk]:
        if self._adapter != "network":
            response = await self.chat_completion(request, session)
            chunk = ChatCompletionChunk(
                id=response.id,
                created=response.created,
                model=response.model,
                choices=[
                    ChunkChoice(
                        index=0,
                        delta=Delta(role="assistant", content=response.choices[0].message.content),
                        finish_reason="stop",
                    )
                ],
                provider_meta=response.provider_meta,
            )
            yield chunk
            return
        
        await self._ensure_page()
        
        conversation_id = request.conversation_id or f"conv-{self._generate_id()}"
        mcp_session = mcp_session_manager.get_or_create_session(conversation_id, self)
        
        file_paths = request.provider_options.get("file_paths", []) if request.provider_options else []
        captured = {"chunks": [], "stream_complete": False}
        
        async def on_response(response):
            url = response.url
            if "/backend-api/f/conversation" not in url:
                return
            try:
                ct = response.headers.get("content-type", "")
                if "text/event-stream" not in ct:
                    return
                body = await response.text()
                captured["chunks"].append({"url": url, "body": body})
                if "event: [DONE]" in body or "event: done" in body:
                    captured["stream_complete"] = True
            except Exception as e:
                logger.debug(f"[network] Response read error: {e}")
        
        self._page.on("response", on_response)
        
        try:
            if file_paths:
                await self._upload_files(file_paths)
            
            user_content = request.messages[-1].get("content", "") if request.messages else ""
            chunks = build_chunked_messages(user_content, chunk_size=self._long_text_chunk_size)
            
            for idx, chunk in enumerate(chunks):
                prefix = f"[Part {idx + 1}/{len(chunks)}] " if len(chunks) > 1 else ""
                await self._send_message(f"{prefix}{chunk}")
                if idx < len(chunks) - 1:
                    await asyncio.sleep(2)
            
            deadline = asyncio.get_event_loop().time() + self._timeout
            while asyncio.get_event_loop().time() < deadline:
                if captured["chunks"] and captured["stream_complete"]:
                    break
                await asyncio.sleep(0.5)
            
            stream_text = ""
            if captured["chunks"]:
                combined = "\n".join(c.get("body", "") for c in captured["chunks"])
                events = parse_sse_chunks(combined)
                stream_text = extract_text_from_sse_events(events)
            
            await self._wait_for_assistant(timeout=self._timeout * 1000)
            dom_text = await self._extract_latest_assistant_text()
            downloads = await extract_download_links(self._page)
            
            response_text = stream_text or dom_text
            
            mcp_session_manager.update_provider_session_id(conversation_id, self._page.url)
            
            full_response = ChatCompletionResponse(
                id=self._generate_id(),
                created=self._current_timestamp(),
                model=request.model,
                choices=[
                    Choice(
                        index=0,
                        message=Message(role="assistant", content=response_text),
                        finish_reason="stop",
                    )
                ],
                usage=Usage(
                    prompt_tokens=len(user_content) // 4,
                    completion_tokens=len(response_text) // 4,
                    total_tokens=(len(user_content) + len(response_text)) // 4,
                ),
                provider_meta={
                    "captured_chunks": len(captured["chunks"]),
                    "stream_complete": captured["stream_complete"],
                    "chunk_urls": [c.get("url") for c in captured["chunks"]],
                    "chunks_sent": len(chunks),
                    "downloads": downloads,
                    "conversation_id": conversation_id,
                },
            )
            
            for choice in full_response.choices:
                content = choice.message.content or ""
                chunk_size = 50
                for i in range(0, len(content), chunk_size):
                    chunk_text = content[i:i + chunk_size]
                    yield ChatCompletionChunk(
                        id=full_response.id,
                        created=full_response.created,
                        model=full_response.model,
                        choices=[
                            ChunkChoice(
                                index=0,
                                delta=Delta(role="assistant" if i == 0 else None, content=chunk_text),
                                finish_reason=None,
                            )
                        ],
                        provider_meta=full_response.provider_meta,
                    )
                    await asyncio.sleep(0.01)
            
            yield ChatCompletionChunk(
                id=full_response.id,
                created=full_response.created,
                model=full_response.model,
                choices=[
                    ChunkChoice(
                        index=0,
                        delta=Delta(),
                        finish_reason="stop",
                    )
                ],
                provider_meta=full_response.provider_meta,
            )
        except PlaywrightTimeout as e:
            raise ProviderTimeoutError(self.provider_id, f"Stream timeout: {e}")
        except Exception as e:
            raise ProviderError(str(e), "stream_completion_failed", self.provider_id)
        finally:
            self._page.remove_listener("response", on_response)
    
    async def list_models(self) -> list[ModelInfo]:
        return [
            ModelInfo(id="chatgpt-web", owned_by="chatgpt-web", provider=self.provider_id),
        ]
    
    async def close(self) -> None:
        try:
            if self._pw:
                await self._pw.stop()
        except Exception as e:
            logger.error(f"Error closing provider {self.provider_id}: {e}")
        finally:
            self._pw = None
            self._browser = None
            self._context = None
            self._page = None


def create_chatgpt_web_provider(
    provider_id: str = "chatgpt-web",
    adapter: str = "dom",
    cdp_url: str = "http://127.0.0.1:9222",
    chatgpt_url: str = "https://chatgpt.com",
    priority: int = 100,
) -> ChatGPTWebProvider:
    config = ProviderConfig(
        provider_id=provider_id,
        provider_type=ProviderType.CHATGPT_WEB,
        enabled=True,
        priority=priority,
        config={
            "cdp_url": cdp_url,
            "chatgpt_url": chatgpt_url,
            "adapter": adapter,
            "headless": False,
            "timeout": 120,
            "long_text_chunk_size": LONG_TEXT_CHUNK_SIZE,
        },
        capabilities=ProviderCapabilities(
            chat_completion=True,
            streaming=(adapter == "network"),
            tools=False,
            vision=False,
            embeddings=False,
            max_context_tokens=128000,
            supported_models=["gpt-4", "gpt-4o", "gpt-3.5-turbo", "chatgpt-web"],
        ),
    )
    return ChatGPTWebProvider(config)
