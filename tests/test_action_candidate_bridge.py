import json
from pathlib import Path

from core import mcp as mcp_module
from core.agent_boundary import infer_action_candidate_payload
from core.mcp import MCPNormalizer
from core.providers import (
    ChatCompletionRequest,
    ChatCompletionResponse,
    Choice,
    Message,
    Provider,
    ProviderCapabilities,
    ProviderConfig,
    ProviderType,
    Usage,
)


class DummyProvider(Provider):
    async def health_check(self):
        return True

    async def chat_completion(self, request, session=None):
        raise NotImplementedError

    async def chat_completion_stream(self, request, session=None):
        raise NotImplementedError

    async def list_models(self):
        return []

    async def close(self):
        return None


def provider():
    return DummyProvider(ProviderConfig(
        provider_id="deepseek-web",
        provider_type=ProviderType.DEEPSEEK_WEB,
        capabilities=ProviderCapabilities(),
    ))


def test_infer_action_candidate_payload_omits_raw_commands():
    req = ChatCompletionRequest(
        model="deepseek-web",
        messages=[{"role": "user", "content": "project: naghsheyar check status with CAG"}],
        provider_options={"agent_boundary": True, "hooshka_context": True},
    )
    meta = {
        "active": True,
        "policy": "hooshka_wg_agent_boundary_v1",
        "delivery": "safe_chat_only",
        "hidden_executable_count": 2,
        "hidden_copy_artifact_count": 1,
        "hidden_hallucination_count": 0,
    }
    payload = infer_action_candidate_payload(req, meta, "deepseek-web")
    assert payload is not None
    assert payload["project"]["id"] == "naghsheyar"
    assert "git.status" in payload["capabilities"]
    assert payload["constraints"]["raw_shell_allowed"] is False
    assert payload["raw_payload_omitted"] is True
    serial = json.dumps(payload, ensure_ascii=False).lower()
    assert "systemctl" not in serial
    assert "journalctl" not in serial
    assert "curl" not in serial
    assert "client access gateway" not in serial


def test_mcp_normalizer_registers_cag_candidate_without_leaking_raw(monkeypatch):
    calls = []

    def fake_register(request, boundary_meta, provider_id):
        calls.append((request, boundary_meta, provider_id))
        return {"enabled": True, "registered": True, "candidate_id": "AC-1234567890abcdef", "state": "queued"}

    monkeypatch.setattr(mcp_module, "register_action_candidate_for_boundary", fake_register)
    req = ChatCompletionRequest(
        model="deepseek-web",
        messages=[{"role": "user", "content": "project: naghsheyar check status with CAG"}],
        provider_options={"agent_boundary": True, "hooshka_context": True},
    )
    response = ChatCompletionResponse(
        id="x",
        created=1,
        model="deepseek-web",
        usage=Usage(),
        choices=[Choice(
            index=0,
            message=Message(role="assistant", content="""CAG = Client Access Gateway

```bash
cd D:\\Code\\naghsheyar
git status
```

Human safe result should remain."""),
            finish_reason="stop",
        )],
    )
    normalized = MCPNormalizer.normalize_response(response, provider(), req)
    content = normalized.choices[0].message.content.lower()
    meta = normalized.provider_meta["agent_boundary"]
    assert calls
    assert meta["action_candidate"]["candidate_id"] == "AC-1234567890abcdef"
    assert "git status" not in content
    assert "client access gateway" not in content
    meta_serial = json.dumps(meta, ensure_ascii=False).lower()
    assert "git status" not in meta_serial
    assert "client access gateway" not in meta_serial


def test_static_gateway_bridge_markers_present():
    text = (Path(__file__).resolve().parents[1] / "core" / "agent_boundary.py").read_text(encoding="utf-8")
    assert "infer_action_candidate_payload" in text
    assert "register_action_candidate_for_boundary" in text
    assert "raw_payload_omitted" in text

