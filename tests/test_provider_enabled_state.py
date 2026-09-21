from adapters.chatgpt_web_provider import create_chatgpt_web_provider
from adapters.deepseek_web_provider import create_deepseek_web_provider
from adapters.qwen_web_provider import create_qwen_web_provider
from adapters.zai_web_provider import create_zai_web_provider


def test_factories_preserve_disabled_inventory_state():
    providers = [
        create_chatgpt_web_provider(enabled=False),
        create_qwen_web_provider(enabled=False),
        create_zai_web_provider(enabled=False),
        create_deepseek_web_provider(enabled=False),
    ]

    assert all(provider.config.enabled is False for provider in providers)
