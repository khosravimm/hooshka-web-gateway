import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import main


@pytest.fixture(scope="module")
def client():
    app = main.create_app(str(ROOT / "config.yaml"))
    app.config["TESTING"] = True
    return app.test_client()


def test_v1_providers_lists_registered_providers(client):
    r = client.get("/v1/providers")
    assert r.status_code == 200
    body = r.get_json()
    assert body["object"] == "list"
    assert isinstance(body["providers"], list) and body["providers"]
    ids = [p["id"] for p in body["providers"]]
    assert "chatgpt-web" in ids
    first = body["providers"][0]
    assert "capabilities" in first
    for key in ("streaming", "tools", "transport_mode", "supported_models", "reasoning", "search"):
        assert key in first["capabilities"]


def test_v1_capabilities_manifest(client):
    r = client.get("/v1/capabilities")
    assert r.status_code == 200
    body = r.get_json()
    assert body["manifest_version"] == "1.0"
    assert body["spec_version"] == "1.0.0-dev.0"
    assert body["compatibility_baseline"] == "openai-2026-09-20"
    assert isinstance(body["providers"], list) and body["providers"]
    assert body["access"]["loopback_without_key"] is True
    assert body["access"]["non_loopback"] == "api_key_required"


def test_modes_still_works(client):
    r = client.get("/modes")
    assert r.status_code == 200
    body = r.get_json()
    assert "providers" in body and body["providers"]


def test_chat_completions_unknown_model_is_404(client):
    r = client.post("/v1/chat/completions", json={
        "model": "no-such-model-xyz",
        "messages": [{"role": "user", "content": "hi"}],
    })
    assert r.status_code == 404
    err = r.get_json()["error"]
    assert err["code"] == "model_not_found"


def test_chat_completions_unknown_provider_is_404(client):
    r = client.post("/v1/chat/completions", json={
        "model": "chatgpt-web",
        "provider": "no-such-provider",
        "messages": [{"role": "user", "content": "hi"}],
    })
    assert r.status_code == 404
    err = r.get_json()["error"]
    assert err["code"] == "unknown_provider"


def test_chat_completions_missing_messages_is_400(client):
    r = client.post("/v1/chat/completions", json={"model": "chatgpt-web"})
    assert r.status_code == 400
    assert r.get_json()["error"]["type"] == "invalid_request_error"

def test_capabilities_publish_versioned_media_contract(client):
    body = client.get("/v1/capabilities").get_json()
    provider = next(p for p in body["providers"] if p["id"] == "deepseek-web")
    media = provider["capabilities"]["media"]
    assert media["contract_version"] == "1.0.0"
    assert media["support"]["text"] is True
    assert media["support"]["image_input"] is False
    for key in ("mime_types", "max_bytes", "max_duration_seconds", "max_resolution", "lifecycle", "privacy"):
        assert key in media["constraints"]["image_input"]

def test_uncertified_image_input_fails_explicitly_before_provider_execution(client):
    r = client.post("/v1/chat/completions", json={
        "model": "deepseek-web",
        "messages": [{"role": "user", "content": [
            {"type": "text", "text": "describe"},
            {"type": "input_image", "image_url": "data:image/png;base64,AA=="},
        ]}],
    })
    assert r.status_code == 400
    err = r.get_json()["error"]
    assert err["code"] == "unsupported_media_type"
    assert err["provider"] == "deepseek-web"
    assert "image_input" in err["details"]["unsupported"]
