from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class LivenessSignal:
    state: str
    reason: str
    matched: bool = False
    reasoning_len: int = 0
    text_len: int = 0
    done: bool = False
    phase: str = ""
    marker_seen: bool = False
    backend_request_seen: bool = False


def classify_model_liveness(
    *,
    matched: bool,
    reasoning_len: int = 0,
    text_len: int = 0,
    done: bool = False,
    phase: str = "",
    error: object = None,
    marker_seen: bool = False,
    backend_request_seen: bool = False,
    previous_reasoning_len: Optional[int] = None,
    previous_text_len: Optional[int] = None,
) -> LivenessSignal:
    """Classify Web-chat run state without using wall-clock timeout as evidence.

    Timeouts remain safety guards. They are not capability evidence. This
    classifier tells a runner whether the current prompt is actually present in
    the provider session and whether the model is thinking/generating, finished,
    errored, or not attached to the current prompt.
    """
    reasoning_len = max(0, int(reasoning_len or 0))
    text_len = max(0, int(text_len or 0))
    phase = str(phase or "")

    if error:
        return LivenessSignal(
            state="ERROR_EVENT",
            reason="provider_session_reported_error",
            matched=matched,
            reasoning_len=reasoning_len,
            text_len=text_len,
            done=done,
            phase=phase,
            marker_seen=marker_seen,
            backend_request_seen=backend_request_seen,
        )
    if marker_seen:
        return LivenessSignal(
            state="MARKER_SEEN",
            reason="expected_marker_seen_in_provider_state",
            matched=matched,
            reasoning_len=reasoning_len,
            text_len=text_len,
            done=done,
            phase=phase,
            marker_seen=True,
            backend_request_seen=backend_request_seen,
        )
    if done or phase == "done":
        return LivenessSignal(
            state="DONE_NO_MARKER",
            reason="provider_session_done_without_expected_marker",
            matched=matched,
            reasoning_len=reasoning_len,
            text_len=text_len,
            done=True,
            phase=phase,
            marker_seen=False,
            backend_request_seen=backend_request_seen,
        )
    if not matched:
        if backend_request_seen:
            return LivenessSignal(
                state="BACKEND_SEEN_NO_PROMPT_MATCH",
                reason="backend_request_seen_but_prompt_not_matched_in_provider_state",
                matched=False,
                reasoning_len=reasoning_len,
                text_len=text_len,
                done=done,
                phase=phase,
                marker_seen=marker_seen,
                backend_request_seen=True,
            )
        return LivenessSignal(
            state="NO_PROMPT_MATCH",
            reason="current_marker_prompt_not_found_in_provider_state",
            matched=False,
            reasoning_len=reasoning_len,
            text_len=text_len,
            done=done,
            phase=phase,
            marker_seen=marker_seen,
            backend_request_seen=False,
        )

    prev_r = reasoning_len if previous_reasoning_len is None else int(previous_reasoning_len)
    prev_t = text_len if previous_text_len is None else int(previous_text_len)
    if text_len > 0:
        if text_len > prev_t:
            reason = "answer_text_delta_observed"
        else:
            reason = "answer_text_present_waiting_for_terminal_or_marker"
        return LivenessSignal(
            state="WAIT_GENERATING",
            reason=reason,
            matched=True,
            reasoning_len=reasoning_len,
            text_len=text_len,
            done=done,
            phase=phase,
            marker_seen=marker_seen,
            backend_request_seen=backend_request_seen,
        )
    if reasoning_len > 0:
        if reasoning_len > prev_r:
            reason = "reasoning_delta_observed"
        else:
            reason = "reasoning_present_waiting_for_answer"
        return LivenessSignal(
            state="WAIT_THINKING",
            reason=reason,
            matched=True,
            reasoning_len=reasoning_len,
            text_len=text_len,
            done=done,
            phase=phase,
            marker_seen=marker_seen,
            backend_request_seen=backend_request_seen,
        )

    return LivenessSignal(
        state="WAIT_SUBMITTED",
        reason="prompt_matched_but_no_reasoning_or_text_yet",
        matched=True,
        reasoning_len=0,
        text_len=0,
        done=done,
        phase=phase,
        marker_seen=marker_seen,
        backend_request_seen=backend_request_seen,
    )
