import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def test_provider_certification_matrix_is_scoped_and_conservative():
    doc=json.loads((ROOT/'docs/governance/HWG_PROVIDER_CERTIFICATION_MATRIX_V1.json').read_text(encoding='utf-8-sig'))
    rows={r['provider_id']:r for r in doc['rows']}
    assert rows['deepseek-web']['status']=='W1_PASS'
    assert rows['deepseek-web']['evidence_level']=='E2_REPEATED_WINDOW'
    assert rows['deepseek-web']['account_id']=='deepseek-web:default-account'
    assert rows['deepseek-web']['model']=='deepseek-web'
    assert rows['chatgpt-web']['status']=='REVALIDATION_REQUIRED'
    assert rows['zai-web']['status']=='REVALIDATION_REQUIRED'
    assert rows['qwen-web']['status']=='HOLD_BLOCKED'
    assert rows['qwen-web']['reason']=='region_restriction'


def test_work013_remains_partial_until_other_scopes_and_interactive_e2_close():
    doc=json.loads((ROOT/'docs/governance/HWG_REMAINING_WORK_REGISTER.json').read_text(encoding='utf-8-sig'))
    item=next(x for x in doc['items'] if x['id']=='HWG-WORK-013')
    assert item['status']=='IN_PROGRESS'
    assert item['latest_evidence']['record']=='docs/evidence/HWG_E3_DEEPSEEK_W1_20260922.md'\n