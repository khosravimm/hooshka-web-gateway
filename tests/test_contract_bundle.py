import json
import sys
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))

import main
from core.contract_bundle import SCHEMA_FILES, compatibility_manifest, load_schema_bundle
from core.governance import rate_limiter


def _fresh_app():
    rate_limiter._buckets.clear()
    app=main.create_app(str(ROOT/'config.yaml'))
    app.config['TESTING']=True
    return app

def test_all_contract_schemas_are_valid_draft_2020_12():
    for filename in SCHEMA_FILES.values():
        doc=json.loads((ROOT/'schemas'/filename).read_text(encoding='utf-8-sig'))
        Draft202012Validator.check_schema(doc)

def test_compatibility_manifest_uses_only_declared_classifications():
    doc=compatibility_manifest()
    allowed=set(doc['classification_values'])
    assert allowed == {'native','normalized','reconstructed','emulated','unsupported','uncertified'}
    assert set(doc['features'].values()) <= allowed

def test_contract_endpoints_and_openapi_cover_live_management_and_agent_routes():
    app=_fresh_app()
    client=app.test_client()
    r=client.get('/v1/contracts/openapi.json'); assert r.status_code==200
    doc=r.get_json(); assert doc['openapi']=='3.1.0'
    assert doc['x-hwg-contract-version']=='1.0.0'
    required={'/v1/chat/completions','/v1/responses','/v1/chat/conversation','/panel/api/providers','/panel/api/accounts','/panel/api/discovery/runs'}
    assert required <= set(doc['paths'])
    for name in ('ProviderProfile','AccountInstance','Capabilities','Error','Event','CompatibilityManifest'):
        assert name in doc['components']['schemas']

def test_schema_and_compatibility_endpoints_are_machine_readable():
    app=_fresh_app()
    client=app.test_client()
    schemas=client.get('/v1/contracts/schemas').get_json()
    assert schemas['contract_version']=='1.0.0'
    assert set(SCHEMA_FILES) <= set(schemas['schemas'])
    compat=client.get('/v1/compatibility').get_json()
    assert compat['manifest_version']=='1.0.0'
    assert compat['features']['multimodal_inputs']=='uncertified'

def test_upload_openapi_contract_is_multipart_and_created_status():
    app=_fresh_app()
    doc=app.test_client().get('/v1/contracts/openapi.json').get_json()
    post=doc['paths']['/v1/uploads']['post']
    assert 'multipart/form-data' in post['requestBody']['content']
    schema=post['requestBody']['content']['multipart/form-data']['schema']
    assert schema['properties']['files']['items']['format']=='binary'
    assert schema['properties']['files']['maxItems']==8
    assert '201' in post['responses']
    assert '/v1/uploads/{upload_id}' in doc['paths']
