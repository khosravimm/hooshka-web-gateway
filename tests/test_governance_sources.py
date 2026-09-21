from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GOV = ROOT / "docs" / "governance"


def test_ng_mission_and_playbook_are_canonical_repository_sources():
    mission = GOV / "HWG_NEXT_GENERATION_PRODUCTION_MISSION_V1.md"
    playbook = GOV / "WEBCHAT_PROVIDER_INTEGRATION_KNOWLEDGE_TRANSFER_V1.md"
    trace = GOV / "HWG_NG_REQUIREMENTS_TRACEABILITY.md"
    assert mission.is_file()
    assert playbook.is_file()
    assert trace.is_file()
    assert "HWG-MISSION-NG-001" in mission.read_text(encoding="utf-8-sig")
    assert "HWG-KT-WEBCHAT-001" in playbook.read_text(encoding="utf-8-sig")


def test_start_here_preserves_normative_authority_and_gap_rule():
    text = (ROOT / "HOOSHKA_WEB_GATEWAY_START_HERE.md").read_text(encoding="utf-8-sig")
    assert "Normative product and control authority" in text
    assert "HWG_NEXT_GENERATION_PRODUCTION_MISSION_V1.md" in text
    assert "WEBCHAT_PROVIDER_INTEGRATION_KNOWLEDGE_TRANSFER_V1.md" in text
    assert "HWG_NG_REQUIREMENTS_TRACEABILITY.md" in text
    assert "tracked gap" in text
