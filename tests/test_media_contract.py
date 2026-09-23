from dataclasses import dataclass
from core.media_contract import requested_media, provider_media_manifest, media_manifest_from_capabilities, validate_media_request
from core.providers import ProviderCapabilities

@dataclass
class FakeConfig:
    config: dict

class FakeProvider:
    provider_id = "fake"
    def __init__(self):
        self.capabilities = ProviderCapabilities(files=True, vision=True, media={
            "image_input": {"supported": True, "constraints": {"mime_types": ["image/png"], "max_bytes": 1024}},
            "audio_input": {"supported": False},
        })
        self.config = FakeConfig({})

def test_requested_media_classifies_message_parts_and_paths():
    rows=requested_media({"messages":[{"content":[{"type":"input_image"},{"type":"input_audio"}]}],"file_paths":["x.pdf","x.bin"]})
    assert [r["kind"] for r in rows] == ["image_input","audio_input","document_upload","file_upload"]

def test_manifest_exposes_support_and_constraint_shape():
    media=provider_media_manifest(FakeProvider())
    assert media["support"]["image_input"] is True
    assert media["constraints"]["image_input"]["mime_types"] == ["image/png"]
    assert media["constraints"]["image_input"]["max_bytes"] == 1024
    assert media["constraints"]["video_input"]["lifecycle"] == "provider_session"

def test_supported_media_request_validates():
    result=validate_media_request(FakeProvider(),{"messages":[{"content":[{"type":"input_image"}]}]})
    assert result["requested"][0]["kind"] == "image_input"


def test_mapping_projection_uses_same_media_contract():
    media=media_manifest_from_capabilities({"vision": True, "files": False})
    assert media["support"]["image_input"] is True
    assert media["support"]["file_upload"] is False
