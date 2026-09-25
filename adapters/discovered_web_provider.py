from __future__ import annotations

import asyncio
from pathlib import Path
from typing import AsyncIterator, Optional, Any
from urllib.parse import urlparse

from core.control_discovery import ENUMERATE_JS
from core.governance import audit_logger
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
        before_by_selector = {str(x.get("selector") or "").strip(): x for x in before_controls if str(x.get("selector") or "").strip()}
        recorded_selector = str((((self._candidate.get("transport") or {}).get("submit") or {}).get("last_verified_selector") or "")).strip()
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
            selector_now = str(item.get("selector") or "").strip()
            previous = before_by_selector.get(selector_now)
            enabled_transition = bool(previous and previous.get("disabled") is True and item.get("disabled") is not True)
            appeared = sig not in before
            semantic = any(token in " ".join([text, aria, title]) for token in ("send", "submit", "arrow_up", "arrow-up"))
            composer_right = float(box.get("x", 0)) + float(box.get("width", 0))
            button_right = float(r.get("x", 0)) + float(r.get("w", 0))
            icon_only = not text and not aria and not title and float(r.get("w", 0)) <= 56 and float(r.get("h", 0)) <= 56
            trailing_icon_action = bool(icon_only and abs(button_right - composer_right) <= 64)
            score = 0
            if selector_now and selector_now == recorded_selector: score += 20
            if enabled_transition: score += 12
            if appeared: score += 6
            if semantic: score += 5
            if trailing_icon_action: score += 4
            if not (selector_now == recorded_selector or enabled_transition or appeared or semantic or trailing_icon_action):
                continue
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

    async def qualify_media(self, media_kind: str, file_path: str, prompt: str, expected_marker: str) -> dict:
        from core.media_qualification import observe_file_upload_surface, qualification_result
        from core.visual_discovery import wait_for_upload_settled, resolve_safe_upload_dialog, media_qualification_preflight
        path=Path(file_path).expanduser().resolve()
        if not path.is_file():
            raise ProviderError(f"File not found: {path}", "file_not_found", self.provider_id)
        page=await self._resolve_page()
        composer, composer_selector, rediscovered=await self._resolve_composer(page)
        response_selector=str((((self._candidate.get("transport") or {}).get("response") or {}).get("selector") or "")).strip()
        if not response_selector:
            raise ProviderError("Certified response selector missing", "response_surface_missing", self.provider_id)
        surface=await observe_file_upload_surface(page)
        preflight=await media_qualification_preflight(page)
        if not preflight.get("allowed"):
            result=qualification_result(self.provider_id,media_kind,str(path),"",expected_marker,advertised=surface)
            result.update({
                "status":"blocked",
                "tested":False,
                "reason":str(preflight.get("reason") or "blocked_by_provider_state"),
                "classification":preflight.get("classification") or {},
                "preflight":preflight,
                "commitment_state":"not_sent",
                "retry_allowed":True,
            })
            return result
        file_input=page.locator("input[type=file]").first
        if await file_input.count()==0:
            raise ProviderError("File input unavailable", "upload_not_supported", self.provider_id)
        before_texts=[str(x).strip() for x in await page.locator(response_selector).all_inner_texts() if str(x).strip()]
        before_controls=await page.evaluate(ENUMERATE_JS)
        await file_input.set_input_files(str(path))
        await page.wait_for_timeout(1200)
        dialog_resolution=await resolve_safe_upload_dialog(page)
        lifecycle=await wait_for_upload_settled(page,self.provider_id,path.name,timeout_seconds=self._timeout)
        if not lifecycle.get("ready"):
            result=qualification_result(self.provider_id,media_kind,str(path),"",expected_marker,advertised=surface)
            result.update({"reason":str(lifecycle.get("reason") or "upload_not_ready"),"classification":lifecycle.get("classification") or {},"visual_evidence":lifecycle.get("trace",[])[-3:],"dialog_resolution":dialog_resolution})
            return result
        self._commitment_state="not_sent"
        await composer.fill(prompt)
        submit, submit_selector=await self._resolve_submit(page,composer,before_controls)
        await submit.click(timeout=5000,no_wait_after=True)
        self._commitment_state="committed"
        response=await self._wait_response(page,before_texts)
        self._commitment_state="terminal"
        result=qualification_result(self.provider_id,media_kind,str(path),response,expected_marker,advertised=surface)
        result.update({"composer_selector":composer_selector,"composer_rediscovered":rediscovered,"submit_selector":submit_selector,"response_selector":response_selector,"upload_ready":True,"dialog_resolution":dialog_resolution})
        return result

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
        from core.visual_discovery import visual_action_gate
        gate = await visual_action_gate(page, "send")
        if not gate.get("allowed"):
            raise ProviderError(
                "Provider UI blocks message submission",
                "blocked_by_visual_state",
                self.provider_id,
                {"classification": gate.get("classification") or {}, "commitment_state":"not_sent", "retry_allowed":True},
            )
        before_texts = [str(x).strip() for x in await page.locator(response_selector).all_inner_texts() if str(x).strip()]
        before_controls = await page.evaluate(ENUMERATE_JS)
        self._commitment_state = "not_sent"
        try:
            await composer.fill(prompt)
            submit, submit_selector = await self._resolve_submit(page, composer, before_controls)
            await submit.click(timeout=5000, no_wait_after=True)
            self._commitment_state = "committed"
            audit_logger.log({
                "event": "provider_send",
                "provider": self.provider_id,
                "model": request.model,
                "transport_mode": "browser_ui_discovered",
                "source": "provider_adapter",
                "commitment_state": "committed",
            })
            content = await self._wait_response(page, before_texts)
            self._commitment_state = "terminal"
            audit_logger.log({
                "event": "provider_result",
                "provider": self.provider_id,
                "model": request.model,
                "transport_mode": "browser_ui_discovered",
                "source": "provider_adapter",
                "outcome": "success",
            })
        except ProviderError:
            if self._commitment_state != "not_sent":
                audit_logger.log({
                    "event": "provider_result",
                    "provider": self.provider_id,
                    "model": request.model,
                    "transport_mode": "browser_ui_discovered",
                    "source": "provider_adapter",
                    "outcome": "failure",
                })
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
