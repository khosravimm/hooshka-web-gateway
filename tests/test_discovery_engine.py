"""Tests for discovery engine pure functions (no browser)."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.discovery_engine import analyze_backend, build_capabilities, diff_drift


def test_analyze_backend_filters_foreign_hosts():
    signals = {"resource_urls": [
        "https://chat.z.ai/backend-api/conversation",
        "https://chat.z.ai/static/app.js",
        "https://chat.z.ai/cdn/assets/_conversation-index.js",
        "https://evil.example.com/api/steal",
        "https://chat.z.ai/sockjs-node",
    ], "stream_hints": ["wss://chat.z.ai/ws"],
        "storage_keys": ["theme", "auth_token_xyz", "chat-history"],
        "config_flags": ["__APP_VERSION"]}
    be = analyze_backend(signals, "chat.z.ai")
    paths = [e["path"] for e in be["candidate_endpoints"]]
    assert "/backend-api/conversation" in paths
    assert not any("evil" in p for p in paths)
    assert "/static/app.js" not in paths
    assert "/cdn/assets/_conversation-index.js" not in paths
    assert be["stream_transports"] == ["wss://chat.z.ai/ws"]
    assert "theme" in be["storage_namespaces"]
    assert not any("token" in k for k in be["storage_namespaces"])
    assert be["secret_like_key_count"] == 1


def test_capabilities_carry_evidence():
    front = {"composer": "TEXTAREA#x", "controls": [
        {"kind": "thinking_toggle", "confidence": "high", "selector": "s1"},
        {"kind": "model_selector", "confidence": "high", "selector": "s2"}]}
    back = {"candidate_endpoints": [{"path": "/api"}], "stream_transports": []}
    caps = {c.name: c for c in build_capabilities(front, back)}
    assert caps["chat"].supported and caps["chat"].evidence.type == "E1"
    assert caps["thinking_control"].supported
    assert caps["thinking_control"].evidence.confidence == "high"
    assert not caps["web_search"].supported
    assert caps["web_search"].evidence.type == "E0"
    assert not caps["streaming"].supported


def test_chat_capability_fails_closed_without_composer():
    caps = {c.name: c for c in build_capabilities({"composer": None, "controls": []}, {"candidate_endpoints": [], "stream_transports": []})}
    assert caps["chat"].supported is False
    assert caps["chat"].evidence.type == "E0"
    assert caps["chat"].evidence.source == "composer not observed"


def test_drift_diff_explicit():
    old = {"controls": [{"kind": "search_toggle", "selector": "s-old"}],
           "candidate_endpoints": [{"path": "/gone"}]}
    new = {"controls": [{"kind": "search_toggle", "selector": "s-new"}],
           "candidate_endpoints": [{"path": "/gone"}, {"path": "/fresh"}]}
    drift = diff_drift(old, new)
    types = {(d["type"], d.get("selector") or d.get("path")) for d in drift}
    assert ("control_added", "s-new") in types
    assert ("control_missing", "s-old") in types
    assert ("endpoint_added", "/fresh") in types
    assert len(drift) == 3


def test_file_upload_capability_uses_observed_file_input_surface():
    front = {"composer": "TEXTAREA#x", "controls": [], "upload_surface": {
        "input_present": True, "advertised_classes": {"image": True, "document": True}
    }}
    back = {"candidate_endpoints": [], "stream_transports": []}
    caps = {c.name: c for c in build_capabilities(front, back)}
    assert caps["file_upload"].supported is True
    assert caps["file_upload"].evidence.type == "E1"
    assert caps["file_upload"].evidence.confidence == "high"
    assert caps["file_upload"].meta["surface"]["advertised_classes"]["document"] is True


def test_upload_surface_drift_is_explicit():
    old = {"controls": [], "candidate_endpoints": [], "upload_surface": {
        "input_present": True, "advertised_classes": {"image": True, "document": False}
    }}
    new = {"controls": [], "candidate_endpoints": [], "upload_surface": {
        "input_present": True, "advertised_classes": {"image": True, "document": True}
    }}
    drift = diff_drift(old, new)
    assert {"type": "upload_class_changed", "class": "document", "old": False, "new": True} in drift


def test_composer_selector_never_falls_back_to_generic_tag():
    from core.discovery_engine import FRONTEND_JS
    assert "candidates.find(unique) || structural(comp)" in FRONTEND_JS
    assert "[contenteditable='true']" in FRONTEND_JS
    assert "else selector = comp.tagName.toLowerCase()" not in FRONTEND_JS
