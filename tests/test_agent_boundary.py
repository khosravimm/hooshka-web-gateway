import json

from core.agent_boundary import (
    apply_request_context_boundary,
    boundary_is_active_for_request,
    enforce_response_boundary,
)
from core.mcp import MCPNormalizer
from core.providers import (
    ChatCompletionRequest,
    ChatCompletionResponse,
    Choice,
    Message,
    ProviderCapabilities,
    ProviderConfig,
    ProviderType,
    Usage,
    Provider,
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


def test_hooshka_context_request_gets_gateway_boundary_prompt():
    req = ChatCompletionRequest(
        model="deepseek-web",
        messages=[{"role": "user", "content": "پروژه: naghsheyar\nمسیر CAG را توضیح بده"}],
    )
    assert boundary_is_active_for_request(req)
    out = apply_request_context_boundary(req)
    assert out.provider_options["agent_boundary"] is True
    assert out.messages[0]["role"] == "system"
    assert "Hooshka Controlled Action Gateway" in out.messages[0]["content"]
    assert "not Client Access Gateway" in out.messages[0]["content"]


def test_tool_protocol_bypasses_implicit_hooshka_human_chat_boundary():
    req = ChatCompletionRequest(
        model="deepseek-web",
        messages=[
            {"role": "system", "content": "Hooshka coding agent with structured tools"},
            {"role": "user", "content": "Create a file using the provided tool"},
        ],
        tools=[{
            "type": "function",
            "function": {
                "name": "write",
                "description": "write a file",
                "parameters": {"type": "object", "properties": {}},
            },
        }],
    )
    assert boundary_is_active_for_request(req) is False
    out = apply_request_context_boundary(req)
    assert out.messages[0]["role"] == "system"
    assert out.messages[0]["content"] == "Hooshka coding agent with structured tools"
    assert not (out.provider_options or {}).get("agent_boundary")


def test_explicit_human_boundary_still_wins_for_tool_request():
    req = ChatCompletionRequest(
        model="deepseek-web",
        messages=[{"role": "user", "content": "Hooshka"}],
        tools=[{"type": "function", "function": {"name": "write", "parameters": {"type": "object"}}}],
        provider_options={"agent_boundary": True},
    )
    assert boundary_is_active_for_request(req) is True


def test_agentic_response_boundary_removes_commands_copy_artifacts_and_bad_cag():
    raw = """CAG = Client Access Gateway

```text
Copy
Download
systemctl status hooshks-web-gateway --no-pager
journalctl -u hooshks-web-gateway -n 200 --no-pager
```

این بخش انسانی باید بماند.

curl http://127.0.0.1:5000/health
"""
    result = enforce_response_boundary(raw)
    safe = result.safe_content.lower()
    assert "client access gateway" not in safe
    assert "systemctl" not in safe
    assert "journalctl" not in safe
    assert "curl" not in safe
    assert "systemctl" not in safe
    assert "journalctl" not in safe
    assert "copy" not in safe
    assert "download" not in safe
    assert "این بخش انسانی باید بماند" in result.safe_content
    assert result.hidden_executable_count >= 2
    assert result.hidden_copy_artifact_count >= 2
    assert result.hidden_hallucination_count >= 1


def test_mcp_normalizer_blocks_agentic_output_before_openai_payload_content():
    req = apply_request_context_boundary(ChatCompletionRequest(
        model="deepseek-web",
        messages=[{"role": "user", "content": "پروژه naghsheyar را با CAG بررسی کن"}],
    ))
    response = ChatCompletionResponse(
        id="x",
        created=1,
        model="deepseek-web",
        usage=Usage(),
        choices=[Choice(
            index=0,
            message=Message(role="assistant", content=r"""CAG = Client Access Gateway

```bash
cd D:\Code\naghsheyar
git status
```

وضعیت فقط با شواهد CAG قابل اعلام است."""),
            finish_reason="stop",
        )],
    )
    normalized = MCPNormalizer.normalize_response(response, provider(), req)
    content = normalized.choices[0].message.content
    meta_json = json.dumps(normalized.provider_meta, ensure_ascii=False).lower()
    assert "client access gateway" not in content.lower()
    assert "git status" not in content.lower()
    assert "d:\\code\\naghsheyar" not in content.lower()
    assert "وضعیت فقط با شواهد" in content
    assert normalized.provider_meta["agent_boundary"]["delivery"] == "safe_chat_only"
    assert normalized.provider_meta["agent_boundary"]["raw_payload_omitted"] is True
    assert "git status" not in meta_json
    assert "client access gateway" not in meta_json


def test_command_name_mentions_are_not_human_chat_content():
    raw = "برای تشخیص، systemctl و journalctl و curl را اجرا کنید. اما وضعیت انسانی این است: نیازمند CAG."
    result = enforce_response_boundary(raw)
    low = result.safe_content.lower()
    assert "systemctl" not in low
    assert "journalctl" not in low
    assert "curl" not in low
    assert "Action Plan / CAG" in result.safe_content
    assert result.hidden_executable_count >= 1
