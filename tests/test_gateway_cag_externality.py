from pathlib import Path
from types import SimpleNamespace

from core.mcp import MCPTranslator, MCPNormalizer
from core.providers import ChatCompletionRequest, ChatCompletionResponse, Choice, Message, Usage

ROOT = Path(__file__).resolve().parents[1]


def test_active_gateway_runtime_has_no_cag_boundary_or_bridge_symbols():
    targets = [
        ROOT / "main.py",
        ROOT / "core" / "mcp.py",
        ROOT / "core" / "tool_contract.py",
        ROOT / "core" / "agent_execution.py",
    ]
    forbidden = (
        "core.agent_boundary",
        "boundary_is_active_for_request",
        "register_action_candidate_for_boundary",
        "HOOSHKA_CAG_BASE_URL",
        "HOOSHKA_WG_CAG_CANDIDATES",
        "ToolAuthorizationMode.CAG",
        "cag_decision",
        "cag_evidence_id",
    )
    for path in targets:
        text = path.read_text(encoding="utf-8-sig")
        for token in forbidden:
            assert token not in text, f"{token} must remain outside HWG runtime: {path}"
    assert not (ROOT / "core" / "agent_boundary.py").exists()


def test_translator_does_not_inject_cag_or_hooshka_policy():
    req = ChatCompletionRequest(
        model="deepseek-web",
        messages=[{"role": "user", "content": "Hooshka CAG project status and run tools"}],
        provider_options={"hooshka_context": True, "agent_boundary": True},
    )
    provider = SimpleNamespace(provider_id="deepseek-web", provider_type=SimpleNamespace(value="deepseek_web"))
    out = MCPTranslator.translate_request(req, provider)
    assert out.messages == req.messages
    assert out.provider_options == req.provider_options
    assert len(out.messages) == 1


def test_normalizer_preserves_executable_model_text_without_cag_rewrite():
    text = "Run python -m unittest discover -v and then report the result."
    response = ChatCompletionResponse(
        id="x", object="chat.completion", created=1, model="deepseek-web",
        choices=[Choice(index=0, message=Message(role="assistant", content=text), finish_reason="stop")],
        usage=Usage(prompt_tokens=0, completion_tokens=1, total_tokens=1), provider_meta={},
    )
    provider = SimpleNamespace(provider_id="deepseek-web", provider_type=SimpleNamespace(value="deepseek_web"))
    normalized = MCPNormalizer.normalize_response(response, provider, request=None)
    assert normalized.choices[0].message.content == text
    assert "agent_boundary" not in normalized.provider_meta
