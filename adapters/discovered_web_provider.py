from __future__ import annotations

import asyncio
from typing import AsyncIterator, Optional, Any
from urllib.parse import urlparse

from core.control_discovery import ENUMERATE_JS
from core.providers import (
    Provider, ProviderCapabilities, ProviderConfig, ProviderError, ProviderType,
    ChatCompletionRequest, ChatCompletionResponse, ChatCompletionChunk,
    Choice, Message, Usage, ModelInfo, SessionContext,
)


class DiscoveredWebProvider(Provider):
    """Generic browser-UI provider materialized from Explorer evidence."""

    def __init__(self, config: ProviderConfig):
        super().__init__(config)
        c = config.config
        self._cdp_url = str(c.get("cdp_url") or "").strip()
        self._home_url = str(c.get("home_url") or "").strip()
        self._candidate = dict(c.get("adapter_candidate") or {})
        self._timeout = float(c.get("timeout_seconds") or 60.0)
        self._pw = None
        self._browser = None
        self._commitment_state = "not_sent"

    async def _connect(self):
        if self._browser is not None:
            return self._browser
        from playwright.async_api import async_playwright
        self._pw = await async_playwright().start()
        self._browser = await self._pw.chromium.connect_over_cdp(self._cdp_url)
        return self._browser

    async def _resolve_page(self):
        browser = await self._connect()
        if not browser.contexts:
            raise ProviderError("Browser context unavailable", "browser_context_missing", self.provider_id)
        ctx = browser.contexts[0]
        origin = urlparse(self._home_url)
        wanted = f"{origin.scheme}://{origin.netloc}"
        pages = [p for p in ctx.pages if p.url.startswith(wanted)]
        if not pages:
            raise ProviderError("Provider page unavailable", "provider_page_missing", self.provider_id)
        composer_sel = str(((self._candidate.get("transport") or {}).get("composer") or {}).get("selector") or "")
        for page in reversed(pages):
            try:
                if composer_sel and await page.locator(composer_sel).count() and await page.locator(composer_sel).first.is_visible():
                    return page
            except Exception:
                pass
        return pages[-1]

    async def _resolve_composer(self, page):
        selector = str(((self._candidate.get("transport") or {}).get("composer") or {}).get("selector") or "").strip()
        if selector:
            loc = page.locator(selector).first
            if await loc.count() and await loc.is_visible():
                return loc, selector, False
        from core.discovery_engine import discover_page
        report = await discover_page(page, self.provider_id)
        fresh = str((report.frontend or {}).get("composer_selector") or "").strip()
        if not fresh:
            raise ProviderError("Composer unavailable after rediscovery", "composer_missing", self.provider_id)
        loc = page.locator(fresh).first
        if not await loc.count() or not await loc.is_visible():
            raise ProviderError("Composer unavailable after rediscovery", "composer_missing", self.provider_id)
        return loc, fresh, True

    @staticmethod
    def _near_composer(item: dict[str, Any], box: dict[str, float]) -> bool:
        r = item.get("rect") or {}
        if not box or not r:
            return False
        cy = float(box.get("y", 0)) + float(box.get("height", 0)) / 2
        iy = float(r.get("y", 0)) + float(r.get("h", 0)) / 2
        left_gap = abs((float(r.get("x", 0)) + float(r.get("w", 0))) - float(box.get("x", 0)))
        right_gap = abs(float(r.get("x", 0)) - (float(box.get("x", 0)) + float(box.get("width", 0))))
        return abs(cy - iy) <= max(90.0, float(box.get("height", 0)) * 3.0) and min(left_gap, right_gap) <= 220.0

    async def _resolve_submit(self, page, composer, before_controls):
        await page.wait_for_timeout(500)
        live = await page.evaluate(ENUMERATE_JS)
        before = {
            (str(x.get("text") or ""), str(x.get("aria") or ""), str(x.get("title") or ""),
             str(x.get("role") or ""), str(x.get("tag") or ""),
             int((x.get("rect") or {}).get("x") or 0), int((x.get("rect") or {}).get("y") or 0))
            for x in before_controls
        }
        box = await composer.bounding_box() or {}
        ranked = []
        for item in live:
            tag = str(item.get("tag") or "").upper()
            role = str(item.get("role") or "").lower()
            if tag != "BUTTON" and role != "button":
                continue
            if item.get("disabled") is True or not self._near_composer(item, box):
                continue
            text = str(item.get("text") or "").strip().lower()
            aria = str(item.get("aria") or "").strip().lower()
            title = str(item.get("title") or "").strip().lower()
            r = item.get("rect") or {}
            sig = (text, aria, title, str(item.get("role") or ""), str(item.get("tag") or ""), int(r.get("x") or 0), int(r.get("y") or 0))
            score = 8 if sig not in before else 0
            if any(token in " ".join([text, aria, title]) for token in ("send", "submit", "arrow_up", "arrow-up")):
                score += 5
            ranked.append((score, item))
        ranked.sort(key=lambda x: x[0], reverse=True)
        if not ranked or ranked[0][0] <= 0:
            raise ProviderError("Live submit control unresolved", "submit_control_missing", self.provider_id)
        selector = str(ranked[0][1].get("selector") or "").strip()
        if not selector:
            raise ProviderError("Live submit selector unavailable", "submit_control_missing", self.provider_id)
        loc = page.locator(selector).first
        if not await loc.count() or not await loc.is_visible():
            raise ProviderError("Live submit control unavailable", "submit_control_missing", self.provider_id)
        return loc, selector

    async def _wait_response(self, page, before_texts: list[str]) -> str:
        selector = str((((self._candidate.get("transport") or {}).get("response") or {}).get("selector") or "")).strip()
        if not selector:
            raise ProviderError("Certified response surface missing", "response_surface_missing", self.provider_id)
        deadline = asyncio.get_running_loop().time() + self._timeout
        last = ""
        stable_since = None
        while asyncio.get_running_loop().time() < deadline:
            await page.wait_for_timeout(350)
            try:
                texts = [str(x).strip() for x in await page.locator(selector).all_inner_texts() if str(x).strip()]
            except Exception:
                texts = []
            if texts:
                candidate = texts[-1]
                changed = len(texts) > len(before_texts) or candidate != (before_texts[-1] if before_texts else "")
                if changed:
                    if candidate != last:
                        last = candidate
                        stable_since = asyncio.get_running_loop().time()
                    elif stable_since is not None and asyncio.get_running_loop().time() - stable_since >= 1.2:
                        return candidate
        raise ProviderError(
            "Committed request did not reach a stable response surface",
            "response_timeout_after_commit",
            self.provider_id,
            {"commitment_state": self._commitment_state, "retry_allowed": False},
        )

    @staticmethod
    def _single_user_text(request: ChatCompletionRequest) -> str:
        messages = list(request.messages or [])
        if len(messages) != 1 or str(messages[0].get("role") or "") != "user":
            raise ProviderError("Discovered provider is only certified for one user message", "message_shape_uncertified")
        content = messages[0].get("content")
        if not isinstance(content, str) or not content.strip():
            raise ProviderError("Text user message required", "message_shape_uncertified")
        return content.strip()

    def supports_model(self, model: str) -> bool:
        return model == self.provider_id

    async def health_check(self) -> bool:
        try:
            page = await self._resolve_page()
            composer, _, _ = await self._resolve_composer(page)
            return bool(await composer.is_visible())
        except Exception:
            return False

    async def list_models(self) -> list[ModelInfo]:
        return [ModelInfo(id=self.provider_id, owned_by="discovered-web", provider=self.provider_id)]

    async def chat_completion(self, request: ChatCompletionRequest, session: Optional[SessionContext] = None) -> ChatCompletionResponse:
        if request.stream:
            raise ProviderError("Streaming is not certified", "streaming_uncertified", self.provider_id)
        if request.tools:
            raise ProviderError("Tools are not certified", "tools_uncertified", self.provider_id)
        if not self.supports_model(request.model):
            raise ProviderError("Unsupported discovered provider model", "invalid_model", self.provider_id)
        prompt = self._single_user_text(request)
        page = await self._resolve_page()
        composer, composer_selector, rediscovered = await self._resolve_composer(page)
        response_selector = str((((self._candidate.get("transport") or {}).get("response") or {}).get("selector") or "")).strip()
        if not response_selector:
            raise ProviderError("Certified response selector missing", "response_surface_missing", self.provider_id)
        before_texts = [str(x).strip() for x in await page.locator(response_selector).all_inner_texts() if str(x).strip()]
        before_controls = await page.evaluate(ENUMERATE_JS)
        self._commitment_state = "not_sent"
        try:
            await composer.fill(prompt)
            submit, submit_selector = await self._resolve_submit(page, composer, before_controls)
            await submit.click(timeout=5000, no_wait_after=True)
            self._commitment_state = "committed"
            content = await self._wait_response(page, before_texts)
            self._commitment_state = "terminal"
        except ProviderError:
            if self._commitment_state == "not_sent":
                try:
                    await composer.fill("")
                except Exception:
                    pass
            raise
        return ChatCompletionResponse(
            id=self._generate_id(), created=self._current_timestamp(), model=request.model,
            choices=[Choice(index=0, message=Message(role="assistant", content=content), finish_reason="stop")],
            usage=Usage(),
            provider_meta={"provider":self.provider_id,"transport_mode":"browser_ui_discovered","commitment_state":self._commitment_state,"retry_allowed":self._commitment_state=="not_sent","composer_selector":composer_selector,"composer_rediscovered":rediscovered,"submit_selector":submit_selector,"response_selector":response_selector},
        )

    async def chat_completion_stream(self, request: ChatCompletionRequest, session: Optional[SessionContext] = None) -> AsyncIterator[ChatCompletionChunk]:
        raise ProviderError("Streaming is not certified", "streaming_uncertified", self.provider_id)
        if False:
            yield None

    async def close(self) -> None:
        if self._pw is not None:
            try:
                await self._pw.stop()
            except Exception:
                pass
        self._pw = None
        self._browser = None


def create_discovered_web_provider(
    provider_id: str,
    *,
    cdp_url: str,
    home_url: str,
    adapter_candidate: dict,
    priority: int = 50,
    enabled: bool = True,
    timeout_seconds: float = 60.0,
) -> DiscoveredWebProvider:
    capabilities = ProviderCapabilities(
        chat_completion=True, streaming=False, streaming_mode="unsupported",
        tools=False, vision=False, embeddings=False, supported_models=[provider_id],
        search=False, reasoning=False, files=False, transport_mode="browser_ui_discovered",
    )
    return DiscoveredWebProvider(ProviderConfig(
        provider_id=provider_id, provider_type=ProviderType.CUSTOM,
        enabled=enabled, priority=priority,
        config={"cdp_url":cdp_url,"home_url":home_url,"adapter_candidate":adapter_candidate,"timeout_seconds":timeout_seconds},
        capabilities=capabilities,
    ))
