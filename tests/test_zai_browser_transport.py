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
