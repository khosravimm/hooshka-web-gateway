from pathlib import Path
import pytest

from adapters.chatgpt_web_provider import create_chatgpt_web_provider
from core.providers import ChatCompletionResponse, Choice, Message, Usage


def test_chatgpt_capabilities_object_is_persistent_for_runtime_certification():
    provider=create_chatgpt_web_provider()
    first=provider.capabilities
    first.files=True
    assert provider.capabilities is first
    assert provider.capabilities.files is True


@pytest.mark.asyncio
async def test_chatgpt_media_qualification_uses_existing_chat_path(monkeypatch):
    provider=create_chatgpt_web_provider()
    captured={}
    async def fake_chat(req, session=None):
        captured['file_paths']=list((req.provider_options or {}).get('file_paths') or [])
        return ChatCompletionResponse(
            id='x', created=1, model='chatgpt-web',
            choices=[Choice(index=0,message=Message(role='assistant',content='HWG_CHATGPT_TEST_MARKER'),finish_reason='stop')],
            usage=Usage(prompt_tokens=0,completion_tokens=0,total_tokens=0),
        )
    monkeypatch.setattr(provider,'chat_completion',fake_chat)
    result=await provider.qualify_media('file_upload','C:/tmp/sample.txt','read','HWG_CHATGPT_TEST_MARKER')
    assert result['status']=='certified'
    assert captured['file_paths']==['C:/tmp/sample.txt']


def test_chatgpt_feature_controls_do_not_require_form_ancestor():
    from pathlib import Path
    src=Path('adapters/chatgpt_web_provider.py').read_text(encoding='utf-8')
    block=src[src.index('async def _apply_feature_controls'):src.index('async def _send_message_via_backend_intercept')]
    assert 'composer has no form ancestor' in block
    assert 'ChatGPT composer form not found' not in block


def test_chatgpt_current_dom_contract_is_covered():
    src=Path('adapters/chatgpt_web_provider.py').read_text(encoding='utf-8')
    assert "button[aria-label='Send']" in src
    assert "[data-markdown-text-style='assistant-message']" in src
    assert "Open profile menu" in src


def test_visual_discovery_accepts_provider_renamed_attachment_stem():
    src=Path('core/visual_discovery.py').read_text(encoding='utf-8')
    assert 'stem_key in body.lower()' in src
