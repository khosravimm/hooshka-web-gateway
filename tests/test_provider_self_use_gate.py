from pathlib import Path
from types import SimpleNamespace

from core.provider_self_use_gate import (
    build_qualification,
    evaluate_qualification,
    load_qualification,
    save_qualification,
    transport_fingerprint,
)


def _provider(profile="p1"):
    return SimpleNamespace(
        provider_id="deepseek-web",
        provider_type=SimpleNamespace(value="web"),
        config=SimpleNamespace(config={"transport_mode":"browser_ui","profile_dir":profile,"cdp_url":"http://127.0.0.1:9330"}),
    )


def _path(ref):
    return {"identified": True, "method": "browser_probe", "evidence_ref": ref}


def test_self_use_gate_requires_all_deterministic_paths_and_roundtrip(tmp_path: Path):
    provider = _provider()
    record = build_qualification(
        provider, _path("send-e1"), _path("receive-e1"), _path("complete-e1"),
        {"tested": True, "passed": True, "tool_class": "deterministic", "evidence_ref": "roundtrip-e2"},
    )
    allowed, reasons = evaluate_qualification(record, provider)
    assert allowed is True and reasons == []
    save_qualification(record, tmp_path)
    loaded = load_qualification(provider.provider_id, tmp_path)
    assert loaded is not None and loaded.transport_fingerprint == transport_fingerprint(provider)


def test_self_use_gate_rejects_missing_roundtrip():
    provider = _provider()
    record = build_qualification(provider, _path("s"), _path("r"), _path("c"), {"tested": False, "passed": False, "tool_class": "deterministic", "evidence_ref": ""})
    allowed, reasons = evaluate_qualification(record, provider)
    assert allowed is False
    assert "roundtrip_not_passed" in reasons
    assert "roundtrip_evidence_missing" in reasons


def test_self_use_gate_rejects_transport_drift():
    provider = _provider("profile-a")
    record = build_qualification(
        provider, _path("s"), _path("r"), _path("c"),
        {"tested": True, "passed": True, "tool_class": "deterministic", "evidence_ref": "rt"},
    )
    changed = _provider("profile-b")
    allowed, reasons = evaluate_qualification(record, changed)
    assert allowed is False
    assert "transport_fingerprint_changed" in reasons


def test_self_use_gate_rejects_nondeterministic_path_method():
    provider = _provider()
    ai_path = {"identified": True, "method": "ai_guess", "evidence_ref": "candidate"}
    record = build_qualification(
        provider, ai_path, _path("r"), _path("c"),
        {"tested": True, "passed": True, "tool_class": "deterministic", "evidence_ref": "rt"},
    )
    allowed, reasons = evaluate_qualification(record, provider)
    assert allowed is False
    assert "send_path_not_qualified" in reasons


def test_self_use_qualification_schema_is_versioned():
    import json
    schema_path=Path('schemas/hwg-provider-self-use-qualification-v1.schema.json')
    schema=json.loads(schema_path.read_text(encoding='utf-8-sig'))
    assert schema['$id']=='urn:hwg:schema:provider-self-use-qualification:1.0.0'
    assert schema['properties']['roundtrip']['$ref']=='#/$defs/roundtripEvidence'
