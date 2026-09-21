"""HWG reference Python client (NG-SDK-003, minimal).

Standard-only surface for external agents: models, chat completions
(incl. SSE streaming), responses, providers, capabilities. Reuses the
``requests`` dependency; no new packages.
"""
from __future__ import annotations

import json

import requests


class HwgError(RuntimeError):
    def __init__(self, message: str, code: str | None = None, status: int | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.status = status


class HwgClient:
    def __init__(self, base_url: str = "http://127.0.0.1:5080",
                 api_key: str | None = None, timeout: float = 240.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._session = requests.Session()
        if api_key:
            self._session.headers["Authorization"] = f"Bearer {api_key}"

    def _get(self, path: str) -> dict:
        r = self._session.get(self.base_url + path, timeout=self.timeout)
        if r.status_code != 200:
            raise HwgError(f"GET {path} -> {r.status_code}", status=r.status_code)
        return r.json()

    def _post(self, path: str, body: dict) -> dict:
        r = self._session.post(self.base_url + path, json=body, timeout=self.timeout)
        if r.status_code != 200:
            code = None
            try:
                code = (r.json().get("error") or {}).get("code")
            except Exception:
                pass
            raise HwgError(f"POST {path} -> {r.status_code}", code=code, status=r.status_code)
        return r.json()

    def models(self) -> list[dict]:
        return self._get("/v1/models")["data"]

    def providers(self) -> list[dict]:
        return self._get("/v1/providers")["providers"]

    def capabilities(self) -> dict:
        return self._get("/v1/capabilities")

    def chat(self, model: str, messages: list[dict], **kwargs) -> dict:
        body = {"model": model, "messages": messages, "stream": False, **kwargs}
        return self._post("/v1/chat/completions", body)

    def chat_stream(self, model: str, messages: list[dict], **kwargs):
        """Yield SSE data payloads (dicts) until [DONE]."""
        body = {"model": model, "messages": messages, "stream": True, **kwargs}
        with self._session.post(self.base_url + "/v1/chat/completions",
                                json=body, timeout=self.timeout, stream=True) as r:
            if r.status_code != 200:
                raise HwgError(f"stream -> {r.status_code}", status=r.status_code)
            for line in r.iter_lines(decode_unicode=True):
                if not line or not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if data == "[DONE]":
                    return
                yield json.loads(data)

    def respond(self, model: str, user_input: str, **kwargs) -> dict:
        return self._post("/v1/responses", {"model": model, "input": user_input, **kwargs})
