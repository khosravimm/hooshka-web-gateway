"""Focus guard: background automation must not steal user focus.

Ported from hwg-next-0.9.3 (hwg/runtime/focus_guard.py). Injection,
extraction, polling, health checks and background navigation must never
bring the browser to the foreground; only explicit user actions
(open/login/CAPTCHA/certification) may, inside a user_initiated() block.
"""

from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Iterator

log = logging.getLogger(__name__)


class FocusViolation(RuntimeError):
    pass


class FocusGuard:
    def __init__(self) -> None:
        self._allow_foreground = False
        self._reason: str | None = None

    @contextmanager
    def user_initiated(self, reason: str) -> Iterator[None]:
        prev, prev_reason = self._allow_foreground, self._reason
        self._allow_foreground, self._reason = True, reason
        log.info("focus.user_initiated reason=%s", reason)
        try:
            yield
        finally:
            self._allow_foreground, self._reason = prev, prev_reason

    def may_bring_to_front(self) -> bool:
        return self._allow_foreground

    def deny(self, action: str) -> None:
        raise FocusViolation(
            f"background action '{action}' attempted to change focus")
