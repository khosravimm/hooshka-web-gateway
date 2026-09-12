from core.model_liveness import classify_model_liveness


def test_liveness_wait_thinking_when_reasoning_present():
    s = classify_model_liveness(matched=True, reasoning_len=120, text_len=0, done=False)
    assert s.state == "WAIT_THINKING"


def test_liveness_wait_generating_when_text_present():
    s = classify_model_liveness(matched=True, reasoning_len=120, text_len=12, done=False)
    assert s.state == "WAIT_GENERATING"


def test_liveness_done_without_marker_is_not_pass():
    s = classify_model_liveness(matched=True, reasoning_len=50, text_len=10, done=True, marker_seen=False)
    assert s.state == "DONE_NO_MARKER"


def test_liveness_marker_seen_is_terminal_candidate():
    s = classify_model_liveness(matched=True, text_len=30, done=True, marker_seen=True)
    assert s.state == "MARKER_SEEN"


def test_liveness_no_prompt_match_is_not_thinking():
    s = classify_model_liveness(matched=False, backend_request_seen=False)
    assert s.state == "NO_PROMPT_MATCH"


def test_liveness_backend_seen_but_no_prompt_match_is_stuck():
    s = classify_model_liveness(matched=False, backend_request_seen=True)
    assert s.state == "BACKEND_SEEN_NO_PROMPT_MATCH"
