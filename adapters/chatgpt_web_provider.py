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
from core.tool_protocol import serialize_messages, parse_tool_envelope, strong_auto_tool_signal

logger = logging.getLogger(__name__)

INPUT_SELECTOR = "#prompt-textarea"
INPUT_SELECTORS = (
    "#prompt-textarea[contenteditable='true']",
    "[contenteditable='true'][role='textbox'][aria-label*='Chat']",
    "textarea[aria-label*='Chat']",
)
SEND_SELECTOR = "button[data-testid='send-button']"
ASSISTANT_SELECTOR = "[data-message-author-role='assistant']"
FILE_INPUT_SELECTOR = "input[type='file']"
UPLOAD_READY_SELECTOR = "button[data-testid='send-button'], text=Upload complete, .upload-complete"
MAX_FILE_UPLOAD_TIMEOUT = 600000
LONG_TEXT_CHUNK_SIZE = 2048
COMPOSER_FILL_THRESHOLD = 8192


class ChatGPTWebProvider(Provider):
    def __init__(self, config: ProviderConfig):
        super().__init__(config)
        self._cdp_url = config.config.get("cdp_url", "http://127.0.0.1:9224")
        self._chatgpt_url = config.config.get("chatgpt_url", "https://chatgpt.com")
        self._adapter = config.config.get("adapter", "dom")
        self._require_authenticated = bool(config.config.get("require_authenticated", True))
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

    async def _session_status(self) -> dict:
        """Return non-secret authentication/UI readiness evidence."""
        if self._page is None:
            return {"authenticated": False, "composer_ready": False}
        try:
            status = await self._page.evaluate(
                """() => {
                  const visible = (el) => !!el && !!(el.offsetWidth || el.offsetHeight || el.getClientRects().length);
                  const profile = [...document.querySelectorAll("[data-testid='accounts-profile-button']")].some(visible);
                  const login = [...document.querySelectorAll("a,button")].some((el) => {
                    if (!visible(el)) return false;
                    const text = (el.innerText || el.textContent || "").trim();
                    return /^(log in|sign up)$/i.test(text);
                  });
                  const composer = [...document.querySelectorAll(
                    "#prompt-textarea[contenteditable='true'],[contenteditable='true'][role='textbox'][aria-label*='Chat'],textarea[aria-label*='Chat']"
                  )].some(visible);
                  return {authenticated: profile && !login, composer_ready: composer};
                }"""
            )
            return {
                "authenticated": bool(status.get("authenticated")),
                "composer_ready": bool(status.get("composer_ready")),
            }
        except Exception:
            return {"authenticated": False, "composer_ready": False}

    async def _require_authenticated_session(self) -> dict:
        status = await self._session_status()
        if self._require_authenticated and not status["authenticated"]:
            raise ProviderError(
                "ChatGPT Web requires an authenticated browser session",
                "auth_required",
                self.provider_id,
            )
        return status

    async def _resolve_composer(self):
        if self._page is None:
            raise ProviderError("Page is not initialized", "page_not_initialized", self.provider_id)
        deadline = asyncio.get_running_loop().time() + 30
        while asyncio.get_running_loop().time() < deadline:
            for selector in INPUT_SELECTORS:
                loc = self._page.locator(selector)
                try:
                    if await loc.count() and await loc.first.is_visible():
                        return loc.first
                except Exception:
                    pass
            await asyncio.sleep(0.25)
        raise PlaywrightTimeout("Timed out waiting for a visible ChatGPT composer")

    @property
    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            chat_completion=True,
            # DOM mode also supports the compatibility streaming endpoint by
            # returning the completed response as a single chunk.  Advertising
            # this capability lets OpenAI-compatible clients such as Kilo
            # select the provider when they send stream=true.
            streaming=True,
            streaming_mode="buffered",
            tools=True,
            vision=False,
            embeddings=False,
            max_context_tokens=128000,
            # Canonical gateway model id. Do not claim arbitrary upstream model
            # aliases that the Web UI does not prove or expose deterministically.
            supported_models=["chatgpt-web"],
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
        await self._require_authenticated_session()

        if len(message) > COMPOSER_FILL_THRESHOLD:
            await self._send_message_via_backend_intercept(message)
            return

        input_box = await self._resolve_composer()
        await input_box.click()
        try:
            await input_box.fill(message)
        except Exception as exc:
            raise ProviderError(
                "Failed to populate ChatGPT composer",
                "composer_input_failed",
                self.provider_id,
            ) from exc

        input_box = await self._resolve_composer()
        actual_length = await input_box.evaluate(
            """el => {
              if (el.value !== undefined) return String(el.value || "").length;
              const children = [...el.children];
              if (children.length) {
                const nl = String.fromCharCode(10);
                return children.map(x => x.textContent || "").join(nl).length;
              }
              return String(el.textContent || "").length;
            }"""
        )
        if int(actual_length or 0) != len(message):
            logger.warning(
                "ChatGPT composer verification failed: expected_len=%s actual_len=%s",
                len(message),
                actual_length,
            )
            raise ProviderError(
                "ChatGPT composer content verification failed",
                "composer_verification_failed",
                self.provider_id,
            )

        send_btn = self._page.locator(SEND_SELECTOR)
        if await send_btn.count() > 0 and await send_btn.is_visible():
            await send_btn.click()
        else:
            raise ProviderError(
                "ChatGPT send button is unavailable",
                "send_button_unavailable",
                self.provider_id,
            )

    async def _send_message_via_backend_intercept(self, message: str):
        """Submit a large prompt through the authenticated frontend backend request.

        The real ChatGPT frontend still performs its normal prepare flow and
        generates all session/Sentinel/proof headers. The gateway only replaces
        the textual message body in the final conversation POST, so large agent
        payloads never have to survive React/ProseMirror composer reconciliation.
        No authentication or proof-token values are read, logged, or persisted.
        """
        if self._page is None:
            raise ProviderError("Page is not initialized", "page_not_initialized", self.provider_id)

        intercepted = asyncio.Event()
        route_pattern = "**/backend-api/f/conversation*"
        carrier = "Hooshka agent request"

        async def replace_final_request(route):
            request = route.request
            try:
                path = request.url.split("chatgpt.com", 1)[-1].split("?", 1)[0]
                if request.method.upper() != "POST" or path != "/backend-api/f/conversation":
                    await route.continue_()
                    return

                import json

                payload = json.loads(request.post_data or "{}")
                messages = payload.get("messages") or []
                if not messages or not isinstance(messages[0], dict):
                    raise ValueError("conversation request has no message payload")
                content = messages[0].get("content") or {}
                parts = content.get("parts") if isinstance(content, dict) else None
                if not isinstance(parts, list) or not parts:
                    raise ValueError("conversation request has no text parts")

                if isinstance(parts[0], str):
                    parts[0] = message
                elif isinstance(parts[0], dict) and "text" in parts[0]:
                    parts[0]["text"] = message
                else:
                    raise ValueError("unsupported ChatGPT message-part shape")

                body = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
                await route.continue_(post_data=body)
                intercepted.set()
            except Exception as exc:
                logger.warning("ChatGPT backend-intercept failed: %s", type(exc).__name__)
                try:
                    await route.abort()
                finally:
                    intercepted.set()

        await self._page.route(route_pattern, replace_final_request)
        try:
            focused = await self._page.evaluate(
                """() => {
                  const selectors = [
                    "#prompt-textarea[contenteditable='true']",
                    "[contenteditable='true'][role='textbox'][aria-label*='Chat']",
                    "textarea[aria-label*='Chat']"
                  ];
                  const visible = (el) => !!el && !!(el.offsetWidth || el.offsetHeight || el.getClientRects().length);
                  for (const selector of selectors) {
                    for (const el of document.querySelectorAll(selector)) {
                      if (!visible(el)) continue;
                      el.focus();
                      return document.activeElement === el || el.contains(document.activeElement);
                    }
                  }
                  return false;
                }"""
            )
            if not focused:
                raise ProviderError(
                    "ChatGPT visible composer could not be focused for backend intercept",
                    "composer_focus_failed",
                    self.provider_id,
                )
            await self._page.keyboard.press("Control+A")
            await self._page.keyboard.press("Backspace")
            await self._page.keyboard.insert_text(carrier)

            send_btn = self._page.locator(SEND_SELECTOR)
            await send_btn.wait_for(state="visible", timeout=15000)
            for _ in range(60):
                if await send_btn.is_enabled():
                    break
                await asyncio.sleep(0.1)
            if not await send_btn.is_enabled():
                raise ProviderError(
                    "ChatGPT send button is unavailable for backend intercept",
                    "send_button_unavailable",
                    self.provider_id,
                )

            await send_btn.click(timeout=15000)
            try:
                await asyncio.wait_for(intercepted.wait(), timeout=20)
            except asyncio.TimeoutError as exc:
                raise ProviderError(
                    "ChatGPT backend conversation request was not intercepted",
                    "backend_intercept_timeout",
                    self.provider_id,
                ) from exc
        finally:
            await self._page.unroute(route_pattern, replace_final_request)

    async def _wait_for_assistant(self, timeout: int = 120000):
        await self._page.wait_for_selector(ASSISTANT_SELECTOR, timeout=timeout)

    async def _wait_for_new_assistant(
        self,
        previous_count: int,
        previous_text: str = "",
        previous_action_count: int = 0,
        timeout: int = 120000,
    ):
        """Wait for a completed assistant response without retaining stale DOM locators."""
        deadline = asyncio.get_running_loop().time() + (timeout / 1000)
        stable_text = None
        stable_samples = 0
        transient = {"thinking", "working", "generating"}

        while asyncio.get_running_loop().time() < deadline:
            # Re-create locators every poll because ChatGPT frequently replaces
            # message nodes while streaming/reconciling React state.
            messages = self._page.locator(ASSISTANT_SELECTOR)
            count = await messages.count()
            text = ""
            if count > 0:
                try:
                    text = (await messages.last.inner_text(timeout=3000)).strip()
                except Exception:
                    text = ""

            is_new = count > previous_count or (count == previous_count and text and text != previous_text)
            if is_new and text and text.lower() not in transient:
                try:
                    action_count = await self._page.locator(
                        "button[data-testid='copy-turn-action-button']"
                    ).count()
                except Exception:
                    action_count = previous_action_count

                generating = False
                for selector in (
                    "button[data-testid='stop-button']",
                    "button[aria-label*='Stop']",
                    "button[aria-label*='stop']",
                ):
                    try:
                        loc = self._page.locator(selector)
                        if await loc.count() and await loc.first.is_visible():
                            generating = True
                            break
                    except Exception:
                        pass

                # Current ChatGPT renders one copy action for the user turn and
                # one for the completed assistant turn. Requiring both protects
                # against accepting the transient assistant placeholder.
                response_actions_ready = action_count >= previous_action_count + 2

                if not generating and response_actions_ready:
                    if text == stable_text:
                        stable_samples += 1
                    else:
                        stable_text = text
                        stable_samples = 1
                    if stable_samples >= 3:
                        return
                else:
                    stable_samples = 0
            else:
                stable_samples = 0

            await asyncio.sleep(0.75)

        raise PlaywrightTimeout(f"Timed out waiting for a completed assistant response after {timeout}ms")

    async def _extract_latest_assistant_text(self) -> str:
        old_text = ""
        stable_samples = 0
        for _ in range(40):
            try:
                messages = self._page.locator(ASSISTANT_SELECTOR)
                if await messages.count() == 0:
                    new_text = ""
                else:
                    new_text = (await messages.last.inner_text(timeout=3000)).strip()
            except Exception:
                try:
                    messages = self._page.locator(ASSISTANT_SELECTOR)
                    if await messages.count() == 0:
                        new_text = ""
                    else:
                        new_text = (
                            await messages.last.evaluate("el => el.innerText || el.textContent || ''")
                        ).strip()
                except Exception:
                    new_text = ""
            if new_text and new_text == old_text:
                stable_samples += 1
                if stable_samples >= 2:
                    break
            else:
                stable_samples = 0
            old_text = new_text
            await asyncio.sleep(0.75)

        try:
            messages = self._page.locator(ASSISTANT_SELECTOR)
            return (await messages.last.inner_text(timeout=3000)).strip()
        except Exception:
            try:
                messages = self._page.locator(ASSISTANT_SELECTOR)
                return (
                    await messages.last.evaluate("el => el.innerText || el.textContent || ''")
                ).strip()
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

    async def _repair_tool_protocol(self, request: ChatCompletionRequest) -> tuple[Optional[str], Optional[list]]:
        """Repair one provider response that violated the strict tool envelope.

        The repair happens inside the same ChatGPT conversation and is bounded
        to a single attempt so protocol failure cannot create an unbounded loop.
        """
        assistant_messages = self._page.locator(ASSISTANT_SELECTOR)
        previous_count = await assistant_messages.count()
        previous_action_count = await self._page.locator(
            "button[data-testid='copy-turn-action-button']"
        ).count()
        previous_text = ""
        if previous_count:
            try:
                previous_text = (await assistant_messages.last.inner_text(timeout=3000)).strip()
            except Exception:
                previous_text = ""

        if request.tool_choice == "required" or isinstance(request.tool_choice, dict):
            repair = (
                "PROTOCOL ERROR: your previous response was not a valid tool call, but this turn requires one. "
                "Do not answer the user's task and do not invent a result. Reply ONLY with one JSON object in "
                "this exact form: {\"tool_calls\":[{\"name\":\"<function_name>\",\"arguments\":{}}]}."
            )
        else:
            repair = (
                "PROTOCOL ERROR: your previous response was not in the required machine envelope. Re-evaluate "
                "the user's latest request. If a listed tool is required, reply ONLY with "
                "{\"tool_calls\":[{\"name\":\"<function_name>\",\"arguments\":{}}]}. If no tool is required, "
                "reply ONLY with {\"final\":\"<complete answer>\"}. Do not add anything outside the JSON."
            )

        await self._send_message(repair)
        await self._wait_for_new_assistant(
            previous_count,
            previous_text,
            previous_action_count=previous_action_count,
            timeout=self._timeout * 1000,
        )
        repaired_text = await self._extract_latest_assistant_text()
        content, calls, valid = parse_tool_envelope(repaired_text)
        if not valid:
            raise ProviderError(
                "Provider failed strict tool protocol after one repair attempt",
                "tool_protocol_violation",
                self.provider_id,
            )
        if (request.tool_choice == "required" or isinstance(request.tool_choice, dict)) and not calls:
            raise ProviderError(
                "Provider returned a final answer when a tool call was required",
                "tool_protocol_violation",
                self.provider_id,
            )
        return content, calls

    async def _review_auto_tool_decision(
        self,
        request: ChatCompletionRequest,
        candidate_final: Optional[str],
    ) -> tuple[Optional[str], Optional[list]]:
        """Review an ``auto`` decision that initially selected a final answer.

        Web-chat models sometimes fabricate local/current state instead of using
        the tools they were given. A bounded review turn corrects that failure
        mode while preserving normal direct answers when no tool is actually
        needed.
        """
        assistant_messages = self._page.locator(ASSISTANT_SELECTOR)
        previous_count = await assistant_messages.count()
        previous_action_count = await self._page.locator(
            "button[data-testid='copy-turn-action-button']"
        ).count()
        previous_text = ""
        if previous_count:
            try:
                previous_text = (await assistant_messages.last.inner_text(timeout=3000)).strip()
            except Exception:
                previous_text = ""

        tool_names = []
        for tool in request.tools or []:
            name = ((tool or {}).get("function") or {}).get("name")
            if name:
                tool_names.append(name)

        review = (
            "TOOL ROUTING REVIEW. Your previous response selected a final answer. Re-check ONLY whether the "
            "user's original request can be answered correctly without any external tool execution. You do NOT "
            "know the user's local machine state, files, installed software, command output, private data, or "
            "fresh external/current state unless a tool result was supplied. If the request depends on any such "
            "state, or explicitly asks to use/run/check through a listed tool, output ONLY a tool_calls JSON "
            "envelope using one of these tools: "
            + ", ".join(tool_names)
            + ". If no tool is genuinely required, output ONLY the final JSON envelope again. Never invent or "
            "simulate a tool result."
        )

        await self._send_message(review)
        await self._wait_for_new_assistant(
            previous_count,
            previous_text,
            previous_action_count=previous_action_count,
            timeout=self._timeout * 1000,
        )
        reviewed_text = await self._extract_latest_assistant_text()
        content, calls, valid = parse_tool_envelope(reviewed_text)
        if not valid:
            return await self._repair_tool_protocol(request)
        return content, calls

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
                except ProviderTimeoutError:
                    # The prompt may already have been submitted. Retrying a
                    # timeout can duplicate the user's turn in ChatGPT Web.
                    raise
                except ProviderError as e:
                    if e.code == "tool_protocol_violation" or e.details.get("submission_started"):
                        raise
                    last_error = e
                    if attempt == 0:
                        logger.warning(f"Chat completion failed, reconnecting: {e}")
                        await self._cleanup_connection()
                        continue
                    break
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
        explicit_conversation = bool(request.conversation_id)
        conversation_id = request.conversation_id or f"conv-{self._generate_id()}"
        mcp_session = mcp_session_manager.get_or_create_session(conversation_id, self)

        # Keep explicitly correlated conversations on their provider URL. Plain
        # stateless completion requests start from a fresh ChatGPT conversation
        # so stale UI history cannot contaminate routing or completion detection.
        if session and session.provider_session_id and str(session.provider_session_id).startswith("https://chatgpt.com/"):
            if self._page.url != session.provider_session_id:
                await self._page.goto(session.provider_session_id, wait_until="domcontentloaded", timeout=30000)
        elif not explicit_conversation and self._page.url != self._chatgpt_url:
            await self._page.goto(self._chatgpt_url, wait_until="domcontentloaded", timeout=30000)

        file_paths = request.provider_options.get("file_paths", []) if request.provider_options else []

        submission_started = False
        try:
            assistant_messages = self._page.locator(ASSISTANT_SELECTOR)
            previous_count = await assistant_messages.count()
            previous_action_count = await self._page.locator(
                "button[data-testid='copy-turn-action-button']"
            ).count()
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

            # OpenAI-compatible agent requests must preserve the complete
            # transcript, tool definitions and prior tool results. Plain chat
            # keeps the shorter legacy path to avoid unnecessary prompt noise.
            if request.tools or any(m.get("role") != "user" for m in request.messages):
                outbound_content = serialize_messages(
                    request.messages,
                    tools=request.tools,
                    tool_choice=request.tool_choice,
                )
            else:
                outbound_content = user_content

            # Agent/tool transcripts are protocol envelopes and must remain one
            # atomic user turn. Splitting them into multiple submitted messages
            # lets ChatGPT answer before the tool schema/transcript is complete.
            if request.tools or any(m.get("role") != "user" for m in request.messages):
                chunks = [outbound_content]
            else:
                chunks = build_chunked_messages(outbound_content, chunk_size=self._long_text_chunk_size)

            for idx, chunk in enumerate(chunks):
                prefix = f"[Part {idx + 1}/{len(chunks)}] " if len(chunks) > 1 else ""
                # Commitment boundary: once submission starts, any later failure
                # is ambiguous from the gateway's perspective and must never
                # trigger an automatic replay of the same user turn.
                submission_started = True
                await self._send_message(f"{prefix}{chunk}")
                if idx < len(chunks) - 1:
                    await asyncio.sleep(2)

            await self._wait_for_new_assistant(
                previous_count,
                previous_text,
                previous_action_count=previous_action_count,
                timeout=self._timeout * 1000,
            )
            response_text = await self._extract_latest_assistant_text()
            downloads = await extract_download_links(self._page)

            content_output = response_text
            tool_calls = None
            finish_reason = "stop"
            if request.tools:
                content_output, tool_calls, valid_protocol = parse_tool_envelope(response_text)
                must_call = request.tool_choice == "required" or isinstance(request.tool_choice, dict)
                if not valid_protocol or (must_call and not tool_calls):
                    content_output, tool_calls = await self._repair_tool_protocol(request)
                elif request.tool_choice in (None, "auto") and not tool_calls:
                    signal = strong_auto_tool_signal(
                        content_output or response_text,
                        request.tools,
                        latest_user_text=user_content,
                    )
                    if signal:
                        logger.info(f"Auto tool review triggered: {signal}")
                        content_output, tool_calls = await self._review_auto_tool_decision(
                            request,
                            content_output,
                        )
                if tool_calls:
                    finish_reason = "tool_calls"

            mcp_session_manager.update_provider_session_id(conversation_id, self._page.url)

            return ChatCompletionResponse(
                id=self._generate_id(),
                created=self._current_timestamp(),
                model=request.model,
                choices=[
                    Choice(
                        index=0,
                        message=Message(
                            role="assistant",
                            content=content_output,
                            tool_calls=tool_calls,
                        ),
                        finish_reason=finish_reason,
                    )
                ],
                usage=Usage(
                    prompt_tokens=len(user_content) // 4,
                    completion_tokens=len(response_text) // 4,
                    total_tokens=(len(outbound_content) + len(response_text)) // 4,
                ),
                provider_meta={
                    "chunks_sent": len(chunks),
                    "downloads": downloads,
                    "conversation_id": conversation_id,
                },
            )
        except PlaywrightTimeout as e:
            err = ProviderTimeoutError(self.provider_id, f"Request timeout: {e}")
            err.details["submission_started"] = submission_started
            raise err
        except ProviderError as e:
            e.details.setdefault("submission_started", submission_started)
            raise
        except Exception as e:
            import traceback
            logger.error(f"Chat completion error: {e}\n{traceback.format_exc()}")
            raise ProviderError(
                str(e),
                "chat_completion_failed",
                self.provider_id,
                details={"submission_started": submission_started},
            )

    async def chat_completion_stream(
        self,
        request: ChatCompletionRequest,
        session: Optional[SessionContext] = None
    ) -> AsyncIterator[ChatCompletionChunk]:
        # Tool calls require protocol normalization after the model response is
        # complete. Use the buffered compatibility path for tools even when the
        # provider is configured for network capture; this preserves a correct
        # OpenAI tool-call contract instead of leaking provider text/DSL.
        if request.tools or self._adapter != "network":
            response = await self.chat_completion(request, session)
            message = response.choices[0].message
            finish_reason = response.choices[0].finish_reason
            chunk = ChatCompletionChunk(
                id=response.id,
                created=response.created,
                model=response.model,
                choices=[
                    ChunkChoice(
                        index=0,
                        delta=Delta(
                            role="assistant",
                            content=message.content,
                            tool_calls=message.tool_calls,
                        ),
                        finish_reason=finish_reason,
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
        await self._ensure_page()
        await self._require_authenticated_session()
        return [
            ModelInfo(id="chatgpt-web", owned_by="chatgpt-web", provider=self.provider_id),
        ]

    async def cancel_active_generation(self, reason: str = "client_cancelled") -> dict:
        """Best-effort ChatGPT Web stop using explicit provider controls only.

        A visible Stop control click is an attempt. It is treated as provider-side
        cancellation evidence only if the explicit Stop control disappears after
        the click. Escape is recorded as an attempt, never as proof.
        """
        result = {"supported": True, "cancelled": False, "reason": reason, "method": "chatgpt_stop_button"}
        page = self._page
        if not page or page.is_closed():
            result["detail"] = "no_active_page"
            return result
        try:
            probe = await page.evaluate(
                """() => {
                  const rect = (el) => {
                    const r = el.getBoundingClientRect();
                    return {x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height)};
                  };
                  const visibleInViewport = (el) => {
                    if (!el) return false;
                    const r = el.getBoundingClientRect();
                    const st = window.getComputedStyle(el);
                    return r.width > 0 && r.height > 0 &&
                      r.bottom >= 0 && r.top <= window.innerHeight &&
                      r.right >= 0 && r.left <= window.innerWidth &&
                      st.visibility !== 'hidden' && st.display !== 'none';
                  };
                  const label = (el) => [
                    el.innerText || '',
                    el.textContent || '',
                    el.getAttribute('aria-label') || '',
                    el.getAttribute('title') || '',
                    el.getAttribute('data-testid') || '',
                    el.id || '',
                    String(el.className || '')
                  ].join(' ').replace(/\\s+/g, ' ').trim();
                  const explicitStop = (el) => {
                    const hay = label(el) + ' ' + (el.outerHTML || '').slice(0, 1200);
                    return /(^|\b)(stop|stop generating|stop streaming|cancel response|interrupt)(\b|$)/i.test(hay) ||
                      el.getAttribute('data-testid') === 'stop-button';
                  };
                  const nodes = Array.from(document.querySelectorAll(
                    'button[data-testid="stop-button"],button[aria-label*="Stop"],button[aria-label*="stop"],button,[role="button"]'
                  ));
                  const candidates = nodes
                    .filter((el) => visibleInViewport(el) && explicitStop(el))
                    .map((el) => ({
                      el,
                      label: label(el).slice(0, 200),
                      rect: rect(el),
                      testid: el.getAttribute('data-testid') || '',
                      aria: el.getAttribute('aria-label') || '',
                      tag: el.tagName.toLowerCase()
                    }));
                  const c = candidates[0];
                  if (!c) return {clicked: false, candidates: 0};
                  c.el.click();
                  return {
                    clicked: true,
                    candidates: candidates.length,
                    label: c.label,
                    rect: c.rect,
                    testid: c.testid,
                    aria: c.aria,
                    tag: c.tag
                  };
                }"""
            )
            escape_sent = False
            if not probe or not probe.get("clicked"):
                try:
                    await page.keyboard.press("Escape")
                    escape_sent = True
                except Exception:
                    pass
            await page.wait_for_timeout(750)
            post = await page.evaluate(
                """() => {
                  const visibleInViewport = (el) => {
                    if (!el) return false;
                    const r = el.getBoundingClientRect();
                    const st = window.getComputedStyle(el);
                    return r.width > 0 && r.height > 0 &&
                      r.bottom >= 0 && r.top <= window.innerHeight &&
                      r.right >= 0 && r.left <= window.innerWidth &&
                      st.visibility !== 'hidden' && st.display !== 'none';
                  };
                  const label = (el) => [
                    el.innerText || '',
                    el.textContent || '',
                    el.getAttribute('aria-label') || '',
                    el.getAttribute('title') || '',
                    el.getAttribute('data-testid') || '',
                    el.id || '',
                    String(el.className || '')
                  ].join(' ').replace(/\\s+/g, ' ').trim();
                  const nodes = Array.from(document.querySelectorAll(
                    'button[data-testid="stop-button"],button[aria-label*="Stop"],button[aria-label*="stop"],button,[role="button"]'
                  ));
                  const remaining = nodes.filter((el) => {
                    if (!visibleInViewport(el)) return false;
                    const hay = label(el) + ' ' + (el.outerHTML || '').slice(0, 1200);
                    return /(^|\b)(stop|stop generating|stop streaming|cancel response|interrupt)(\b|$)/i.test(hay) ||
                      el.getAttribute('data-testid') === 'stop-button';
                  });
                  return {remaining_stop_controls: remaining.length};
                }"""
            )
            result.update(probe or {})
            result["escape_sent"] = escape_sent
            result["attempted"] = bool((probe or {}).get("clicked")) or escape_sent
            # A click is necessary but not sufficient; disappearance of the
            # explicit Stop control is the minimum provider-side confirmation.
            result.update(post or {})
            result["cancelled"] = bool((probe or {}).get("clicked")) and int((post or {}).get("remaining_stop_controls") or 0) == 0
        except Exception as exc:
            result["error"] = str(exc)[:240]
        return result

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
    cdp_url: str = "http://127.0.0.1:9224",
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
            "require_authenticated": True,
            "headless": False,
            "timeout": 120,
            "long_text_chunk_size": LONG_TEXT_CHUNK_SIZE,
        },
        capabilities=ProviderCapabilities(
            chat_completion=True,
            # DOM provides buffered compatibility streaming; network mode can
            # additionally capture provider events. Tools use the buffered
            # path so their protocol can be normalized before emission.
            streaming=True,
            streaming_mode="buffered",
            tools=True,
            vision=False,
            embeddings=False,
            max_context_tokens=128000,
            supported_models=["chatgpt-web"],
        ),
    )
    return ChatGPTWebProvider(config)
