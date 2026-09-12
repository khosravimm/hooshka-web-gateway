from pathlib import Path


def test_zai_transport_records_liveness_state():
    src = Path("adapters/zai_browser_transport.py").read_text(encoding="utf-8")
    assert "from core.model_liveness import classify_model_liveness" in src
    assert "self.last_liveness" in src
    assert "classify_model_liveness(" in src
    assert "reasoning_len" in src
    assert "backend_request_seen" in src


def test_zai_provider_exposes_liveness_in_browser_observability():
    src = Path("adapters/zai_web_provider.py").read_text(encoding="utf-8")
    assert "last_liveness" in src
    assert "liveness" in src
    assert "browser_observability" in src
