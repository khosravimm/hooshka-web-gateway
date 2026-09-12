from pathlib import Path


def test_qwen_browser_transport_event_risk_detection_is_wired():
    src = Path("adapters/qwen_browser_transport.py").read_text(encoding="utf-8")

    assert "from core.provider_risk import detect_provider_risk" in src
    assert "visible_risk_text" in src
    assert "daily usage limit" in src
    assert "slide to verify" in src
    assert "visible_signal = detect_provider_risk" in src
    assert "has_event: matched && !!msg" in src
    assert "has_event: matched && !!ms," not in src
