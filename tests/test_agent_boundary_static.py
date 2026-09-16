from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_chat_routes_pass_request_to_normalizer_for_boundary():
    text = (ROOT / "main.py").read_text(encoding="utf-8-sig")
    assert "normalize_response(response, provider, translated_req)" in text
    assert "boundary_is_active_for_request(req)" in text
    assert "enforce_response_boundary" in text


def test_agent_boundary_module_does_not_store_raw_commands_in_meta():
    text = (ROOT / "core" / "agent_boundary.py").read_text(encoding="utf-8-sig")
    assert "raw_payload_omitted" in text
    assert "safe_chat_only" in text
    assert "Action Plan / CAG" in text
    assert "Client Access Gateway" in text
    assert "Hooshka Controlled Action Gateway" in text
    meta_start = text.index("def meta")
    meta_body = text[meta_start:text.index("\ndef _message_text", meta_start)]
    assert "safe_content" not in meta_body
    assert "content" not in meta_body
