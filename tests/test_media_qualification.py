import asyncio
import json
from pathlib import Path

from core.media_qualification import parse_accept, apply_persisted_media_certification, qualification_result, media_qualification_policy
from core.providers import ProviderCapabilities
from core.profile_store import update_provider_media_qualification


def test_accept_parser_classifies_provider_surface():
    x=parse_accept('.txt,.md,.pdf,.docx,.csv,.xlsx,.png,.jpg,.py,.js,.pptx')
    assert x['classes']['text'] is True
    assert x['classes']['document'] is True
    assert x['classes']['spreadsheet'] is True
    assert x['classes']['image'] is True
    assert x['classes']['code'] is True
    assert x['classes']['presentation'] is True
    assert x['classes']['audio'] is False


def test_qualification_does_not_certify_without_marker():
    x=qualification_result('p','image_input','x.png','wrong','EXPECTED')
    assert x['status']=='failed'
    assert x['evidence_level']=='E1'
    assert x['certified']['image_input'] is False


def test_apply_persisted_certification_enables_only_e2_media():
    class P: pass
    p=P(); p.provider_id='p'; p.capabilities=ProviderCapabilities()
    inv={'provider_profiles':[{'provider_id':'p','media_qualification':{'latest':{'certified':{'file_upload':True,'image_input':True},'constraints':{'mime_types':['image/png']}}}}]}
    certified=apply_persisted_media_certification(p,inv)
    assert certified['file_upload'] is True
    assert p.capabilities.files is True
    assert p.capabilities.vision is True
    assert p.capabilities.media['image_input']['supported'] is True


def test_profile_persistence_merges_certifications(tmp_path):
    root=tmp_path/'store'; d=root/'provider_profiles'; d.mkdir(parents=True)
    path=d/'p.json'; path.write_text(json.dumps({'provider_id':'p','profile_id':'p:default','change_log':[]}),encoding='utf-8')
    update_provider_media_qualification('p',{'certified':{'file_upload':True,'image_input':False},'evidence_level':'E2'},root)
    out=update_provider_media_qualification('p',{'certified':{'file_upload':True,'image_input':True},'evidence_level':'E2'},root)
    latest=out['media_qualification']['latest']['certified']
    assert latest=={'file_upload':True,'image_input':True}


def test_policy_applies_to_all_current_and_future_providers():
    policy=media_qualification_policy()
    assert policy["required"] is True
    assert policy["scope"]=="all_current_and_future_providers"
    assert policy["promotion_rule"]=="E2_required_for_certified"
    assert {"text","document","spreadsheet","image","code","presentation","audio","video"} <= set(policy["classes"])


def test_qualification_records_media_class():
    x=qualification_result('p','file_upload','sheet.xlsx','HWG_X','HWG_X')
    assert x['media_class']=='spreadsheet'
    assert x['certified_classes']=={'spreadsheet':True}


def test_profile_persistence_merges_certified_classes(tmp_path):
    root=tmp_path/'store'; d=root/'provider_profiles'; d.mkdir(parents=True)
    path=d/'p.json'; path.write_text(json.dumps({'provider_id':'p','profile_id':'p:default','change_log':[]}),encoding='utf-8')
    update_provider_media_qualification('p',{'certified':{'file_upload':True},'certified_classes':{'document':True},'evidence_level':'E2'},root)
    out=update_provider_media_qualification('p',{'certified':{'file_upload':True},'certified_classes':{'spreadsheet':True},'evidence_level':'E2'},root)
    classes=out['media_qualification']['latest']['certified_classes']
    assert classes=={'document':True,'spreadsheet':True}


def test_accept_parser_maps_mime_wildcards_to_classes():
    x=parse_accept('image/*,video/*,audio/*,text/plain')
    assert x['classes']['image'] is True
    assert x['classes']['video'] is True
    assert x['classes']['audio'] is True
    assert x['classes']['text'] is True
