from core.control_discovery import ENUMERATE_JS


def test_enumerator_does_not_deduplicate_similar_controls_by_html_prefix():
    # querySelectorAll already returns unique DOM nodes. Prefix-based outerHTML
    # dedup can collapse distinct sibling controls such as DeepThink/Search.
    assert "outerHTML" not in ENUMERATE_JS
    assert "const seen = new Set()" not in ENUMERATE_JS
    assert "[tabindex=\"0\"]" in ENUMERATE_JS
