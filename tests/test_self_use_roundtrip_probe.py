import asyncio
from types import SimpleNamespace

import pytest

from core.self_use_roundtrip_probe import controlled_roundtrip, validate_path_evidence


def _paths():
    return {
        "send_path":{"identified":True,"method":"browser_probe","evidence_ref":"send-e1"},
        "receive_path":{"identified":True,"method":"network","evidence_ref":"receive-e1"},
        "completion_path":{"identified":True,"method":"dom","evidence_ref":"complete-e1"},
    }


class _Provider:
    provider_id="deepseek-web"
    provider_type=SimpleNamespace(value="web")
    config=SimpleNamespace(config={"profile_dir":"p1","cdp_url":"http://127.0.0.1:9330"})
    def __init__(self, exact=True): self.exact=exact
    async def chat_completion(self, request):
        token=request.messages[0]["content"].rsplit(": ",1)[-1]
        text=token if self.exact else "WRONG"
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=text))])


def test_path_evidence_must_be_deterministic():
    bad=_paths(); bad["send_path"]={"identified":True,"method":"ai_guess","evidence_ref":"x"}
    with pytest.raises(ValueError, match="send_path_not_deterministic"):
        validate_path_evidence(bad)


def test_roundtrip_requires_execution_authority(tmp_path):
    with pytest.raises(PermissionError):
        asyncio.run(controlled_roundtrip(_Provider(),"m",_paths(),execution_authority="",root=tmp_path))


def test_successful_roundtrip_creates_qualification(tmp_path):
    result=asyncio.run(controlled_roundtrip(_Provider(True),"m",_paths(),execution_authority="automated_validation",root=tmp_path))
    assert result["passed"] is True
    assert result["allowed"] is True
    assert result["record_path"]


def test_failed_roundtrip_does_not_create_qualification(tmp_path):
    result=asyncio.run(controlled_roundtrip(_Provider(False),"m",_paths(),execution_authority="automated_validation",root=tmp_path))
    assert result["passed"] is False
    assert result["allowed"] is False
    assert result["record_path"] is None


def test_adapter_transport_paths_are_identified_before_live_send():
    from core.self_use_roundtrip_probe import identify_deterministic_transport_paths
    paths=identify_deterministic_transport_paths(_Provider())
    validate_path_evidence(paths)
    assert paths['send_path']['evidence_ref'].startswith('adapter-source:')
    assert paths['receive_path']['identified'] is True
    assert paths['completion_path']['identified'] is True
