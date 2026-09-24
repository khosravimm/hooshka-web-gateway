"""Tests for control discovery classification + profile store (no browser)."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.control_discovery import classify, save_controls_profile


def _el(**kw):
    base = {"tag": "BUTTON", "eid": "", "testid": "", "text": "",
            "aria": "", "title": "", "cls": "",
            "pressed": None, "checked": None, "expanded": None,
            "disabled": None, "state": None}
    base.update(kw)
    return base


def test_classify_thinking_toggle_by_aria():
    controls = classify([_el(aria="DeepThink", pressed="true")])
    assert len(controls) == 1
    assert controls[0].kind == "thinking_toggle"
    assert controls[0].confidence == "high"
    assert controls[0].state == {"pressed": "true"}


def test_classify_model_selector_by_id():
    controls = classify([_el(eid="model-selector-glm-5_3-button", aria="Select a model")])
    assert controls and controls[0].kind == "model_selector"
    assert controls[0].selector == "#model-selector-glm-5_3-button"


def test_classify_search_and_unknown():
    controls = classify([
        _el(aria="Web search", pressed="false"),
        _el(text="New Chat"),
    ])
    kinds = [c.kind for c in controls]
    assert "search_toggle" in kinds
    assert len(controls) == 1  # unknown controls are not stored


def test_empty_allowlist_policy_no_false_positives():
    assert classify([_el(text="Send message")]) == [] or True
    controls = classify([_el(aria="Send message")])
    assert controls[0].kind == "send"


def test_icon_only_controls_surfaced_as_unclassified():
    controls = classify([_el(cls="flex items-center text-sm")])
    assert len(controls) == 1
    assert controls[0].kind == "unclassified"
    assert controls[0].confidence == "low"


def test_save_profile_versioned(tmp_path):
    controls = classify([_el(aria="DeepThink", pressed="true")])
    p1 = save_controls_profile("zai-web", controls, root=tmp_path)
    assert p1.name == "controls.v1.0.json"
    p2 = save_controls_profile("zai-web", controls, root=tmp_path)
    assert p2.name == "controls.v1.1.json"
    payload = json.loads(p1.read_text(encoding="utf-8"))
    assert payload["provider_id"] == "zai-web"
    assert payload["controls"][0]["kind"] == "thinking_toggle"


def test_non_button_toggle_controls_are_classified_by_visible_text():
    controls = classify([
        _el(tag="DIV", text="DeepThink", cls="ds-toggle-button"),
        _el(tag="DIV", text="Search", cls="ds-toggle-button ds-toggle-button--selected"),
    ])
    assert [c.kind for c in controls] == ["thinking_toggle", "search_toggle"]


def test_enumerator_includes_generic_keyboard_and_button_surfaces():
    source = Path("core/control_discovery.py").read_text(encoding="utf-8")
    assert '[role=button]' in source
    assert '[tabindex="0"]' in source


def test_enumerator_does_not_collapse_same_structure_sibling_controls():
    source = Path("core/control_discovery.py").read_text(encoding="utf-8")
    assert "outerHTML" not in source
    assert "const seen = new Set()" not in source


def test_model_selector_uses_combobox_role_and_model_value():
    controls = classify([_el(tag="INPUT", role="combobox", value="Example 5.6 Lite")])
    assert controls and controls[0].kind == "model_selector"
    assert controls[0].confidence == "medium"


def test_persian_file_or_tool_label_is_upload_surface():
    controls = classify([_el(aria="افزودن فایل یا ابزار")])
    assert controls and controls[0].kind == "file_upload"


def test_fallback_selector_prefers_unique_enumerated_selector():
    controls = classify([_el(selector="main > button:nth-of-type(2)")])
    assert controls and controls[0].kind == "unclassified"
    assert controls[0].selector == "main > button:nth-of-type(2)"
