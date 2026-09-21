"""Submission commitment tracking (ported from hwg-next-0.9.3).

Boundary: NOT_SENT -> MAYBE_SENT -> COMMITTED -> TERMINAL.
Retry is only safe before anything was sent; after a possibly-committed
submission, replay is forbidden. Complements the provider-level
submission_started flag with a reusable state machine.
"""

from __future__ import annotations

import logging
from enum import Enum

log = logging.getLogger(__name__)


class Commitment(str, Enum):
    NOT_SENT = "not_sent"
    MAYBE_SENT = "maybe_sent"
    COMMITTED = "committed"
    TERMINAL = "terminal"


class CommitmentError(RuntimeError):
    pass


class CommitmentTracker:
    _ALLOWED = {
        Commitment.NOT_SENT: {Commitment.MAYBE_SENT, Commitment.TERMINAL},
        Commitment.MAYBE_SENT: {Commitment.COMMITTED, Commitment.TERMINAL},
        Commitment.COMMITTED: {Commitment.TERMINAL},
        Commitment.TERMINAL: set(),
    }

    def __init__(self, correlation_id: str) -> None:
        self.correlation_id = correlation_id
        self._state = Commitment.NOT_SENT

    @property
    def state(self) -> Commitment:
        return self._state

    def advance(self, target: Commitment) -> None:
        if target not in self._ALLOWED[self._state]:
            raise CommitmentError(
                f"illegal transition {self._state} -> {target} (cid={self.correlation_id})")
        log.info("commitment.transition cid=%s %s->%s",
                 self.correlation_id, self._state.value, target.value)
        self._state = target

    def may_retry(self) -> bool:
        return self._state == Commitment.NOT_SENT

    def require_retry_safe(self) -> None:
        if not self.may_retry():
            raise CommitmentError(
                f"retry forbidden at state={self._state.value} (cid={self.correlation_id})")
