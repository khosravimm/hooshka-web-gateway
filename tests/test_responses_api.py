import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pytest

import main


@pytest.fixture(scope="module")
def client():
    app = main.create_app(str(ROOT / "config.yaml"))
    app.config["TESTING"] = True
    return app.test_client()


def test_responses_rejects_streaming_explicitly(client):
    r = client.post("/v1/responses", json={"model": "chatgpt-web", "input": "hi", "stream": True})
    assert r.status_code == 400
    assert r.get_json()["error"]["code"] == "unsupported_streaming"


def test_responses_unknown_model_is_404(client):
    r = client.post("/v1/responses", json={"model": "no-such-model-xyz", "input": "hi"})
    assert r.status_code == 404
    assert r.get_json()["error"]["code"] == "model_not_found"


def test_responses_unknown_provider_is_404(client):
    r = client.post("/v1/responses", json={
        "model": "chatgpt-web", "provider": "no-such-provider", "input": "hi"})
    assert r.status_code == 404
    assert r.get_json()["error"]["code"] == "unknown_provider"


def test_responses_empty_input_is_400(client):
    r = client.post("/v1/responses", json={"model": "chatgpt-web", "input": "   "})
    assert r.status_code == 400
