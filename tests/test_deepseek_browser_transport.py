from pathlib import Path

from adapters.deepseek_browser_transport import DeepSeekBrowserUITransport


def test_deepseek_security_check_text_with_composer_is_not_captcha():
    signals = DeepSeekBrowserUITransport._block_signals(
        "Review security check handling in application code",
        textarea_count=1,
        url="https://chat.deepseek.com/a/chat/s/example",
        visible_risk_count=0,
    )
    assert signals["captcha"] is False
    assert signals["login"] is False


def test_deepseek_visible_risk_node_is_captcha():
    signals = DeepSeekBrowserUITransport._block_signals(
        "ordinary page text",
        textarea_count=1,
        url="https://chat.deepseek.com/a/chat/s/example",
        visible_risk_count=1,
    )
    assert signals["captcha"] is True


def test_deepseek_no_composer_security_check_is_captcha():
    signals = DeepSeekBrowserUITransport._block_signals(
        "security check",
        textarea_count=0,
        url="https://chat.deepseek.com/",
        visible_risk_count=0,
    )
    assert signals["captcha"] is True


def test_deepseek_visible_risk_selector_excludes_generic_divs():
    text = Path("adapters/deepseek_browser_transport.py").read_text(encoding="utf-8")
    assert ".captcha,.cf-turnstile,iframe" in text
    assert "button,[role=\"button\"],div,section" not in text.split("async def _visible_risk_count", 1)[1].split("@staticmethod", 1)[0]
