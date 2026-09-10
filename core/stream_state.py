import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class StreamState(str, Enum):
    CONNECTING = "CONNECTING"
    HEADERS_RECEIVED = "HEADERS_RECEIVED"
    WAITING_FIRST_EVENT = "WAITING_FIRST_EVENT"
    STREAMING = "STREAMING"
    TOOL_AMBIGUOUS = "TOOL_AMBIGUOUS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


@dataclass
class StreamTracker:
    request_id: str
    state: StreamState = StreamState.CONNECTING
    started_at: float = field(default_factory=time.monotonic)
    headers_at: Optional[float] = None
    first_event_at: Optional[float] = None
    last_meaningful_event_at: Optional[float] = None
    completed_at: Optional[float] = None
    parsed_events: int = 0
    bytes_received: int = 0
    terminal_reason: Optional[str] = None

    def headers_received(self) -> None:
        now = time.monotonic()
        self.headers_at = now
        self.state = StreamState.WAITING_FIRST_EVENT

    def meaningful_event(self, byte_count: int = 0) -> None:
        now = time.monotonic()
        if self.first_event_at is None:
            self.first_event_at = now
        self.last_meaningful_event_at = now
        self.parsed_events += 1
        self.bytes_received += max(0, byte_count)
        self.state = StreamState.STREAMING

    def complete(self, reason: str = "completed") -> None:
        self.completed_at = time.monotonic()
        self.terminal_reason = reason
        self.state = StreamState.COMPLETED

    def fail(self, reason: str) -> None:
        self.completed_at = time.monotonic()
        self.terminal_reason = reason
        self.state = StreamState.FAILED

    def cancel(self, reason: str = "cancelled") -> None:
        self.completed_at = time.monotonic()
        self.terminal_reason = reason
        self.state = StreamState.CANCELLED

    @property
    def time_to_first_event(self) -> Optional[float]:
        if self.first_event_at is None:
            return None
        return self.first_event_at - self.started_at
