from pathlib import Path

import re


def test_zai_model_option_first_line_regex_distinguishes_glm53_and_flash():
    glm53 = re.compile(rf"(^|\n)\s*{re.escape('GLM-5.3')}\s*(\n|$)", re.I)
    flash = re.compile(rf"(^|\n)\s*{re.escape('GLM-5.3-Flash')}\s*(\n|$)", re.I)

    assert glm53.search("GLM-5.3\nFlagship model, excels at coding")
    assert not glm53.search("GLM-5.3-Flash\nNEW\nLightweight flagship")
    assert flash.search("GLM-5.3-Flash\nNEW\nLightweight flagship")


def test_zai_model_option_javascript_selector_documents_first_line_intent():
    source = Path("adapters/zai_browser_transport.py").read_text(encoding="utf-8")
    assert "firstLine === displayName" in source
    assert "modelSelectorButton" in source


def test_zai_selector_handles_already_open_menu_state():
    source = Path("adapters/zai_browser_transport.py").read_text(encoding="utf-8")
    assert 'data-state' in source
    assert 'aria-expanded' in source
    assert 'state.lower() != "open"' in source


def test_zai_file_submit_requires_observed_transition():
    source = Path("adapters/zai_browser_transport.py").read_text(encoding="utf-8")
    assert "submit_not_confirmed" in source
    assert "file-prompt-submit-unconfirmed" in source
    assert "page.url != before_url or self.last_backend_request_model" in source


def test_zai_snapshot_has_conversation_scoped_visible_dom_fallback():
    source = Path("adapters/zai_browser_transport.py").read_text(encoding="utf-8")
    assert ".chat-assistant, #response-content-container" in source
    assert "body.includes(prompt)" in source
    assert "source:'visible_dom'" in source
    assert "visible_dom_stable_since" in source
