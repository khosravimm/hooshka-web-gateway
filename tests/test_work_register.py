import json
from pathlib import Path

from core.work_register import load_register, summarize_register, validate_register

def test_remaining_work_register_is_valid_and_nonempty():
    doc=load_register()
    assert doc["register_id"]=="HWG-WORK-REGISTER-001"
    assert len(doc["items"]) >= 16
    assert validate_register(doc)==[]
    assert any(x["priority"]=="P0" and x["status"]!="DONE" for x in doc["items"])

def test_work_summary_exposes_next_actions_and_counts():
    s=summarize_register(load_register())
    assert s["open"] > 0
    assert s["p0_open"] > 0
    assert s["next_actions"]

def test_control_plane_exposes_work_register_workspace():
    html=Path("control_panel_ui/index.html").read_text(encoding="utf-8-sig")
    js=Path("control_panel_ui/panel.js").read_text(encoding="utf-8-sig")
    src=Path("control_panel.py").read_text(encoding="utf-8-sig")
    assert 'data-panel="work"' in html
    assert "panel-work" in html
    assert "loadWorkRegister" in js
    assert "/api/governance/work-register" in src


def test_done_items_require_evidence_and_completion_time():
    doc = load_register()
    sample = dict(doc["items"][0])
    sample["id"] = "HWG-WORK-TEST"
    sample["status"] = "DONE"
    sample.pop("evidence", None)
    sample.pop("completed_at", None)
    probe = {**doc, "items": [sample]}
    errors = validate_register(probe)
    assert any("DONE without evidence" in e for e in errors)
    assert any("DONE without completed_at" in e for e in errors)
